import logging
import time

import fastapi

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app import llm
from app.explanations import explain_in_background, fallback_text
from app.models import Alert, Transaction
from app.schemas import ScoreOut, TransactionIn
from app.scoring import ml
from app.scoring.pipeline import score_transaction

router = APIRouter(tags=["scoring"])
logger = logging.getLogger(__name__)


@router.post("/score", response_model=ScoreOut)
def score(txn: TransactionIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    started = time.perf_counter()
    result = score_transaction(db, txn)

    rules = [{"code": h.code, "message": h.message, "weight": h.weight} for h in result.rule_hits]
    row = Transaction(
        step=txn.step, type=txn.type, amount=txn.amount,
        name_orig=txn.name_orig, oldbalance_org=txn.oldbalance_org, newbalance_orig=txn.newbalance_orig,
        name_dest=txn.name_dest, oldbalance_dest=txn.oldbalance_dest, newbalance_dest=txn.newbalance_dest,
        features=result.features, rule_flags=rules, rule_score=result.rule_score,
        xgb_proba=result.xgb_proba, anomaly_percentile=result.anomaly_percentile,
        similarity_score=result.similarity_score, combined_score=result.combined_score,
        decision=result.decision, true_label=txn.true_label,
    )
    db.add(row)
    db.flush()

    alert, reasons, explanation = None, [], None
    if result.decision != "approve":
        try:
            reasons = ml.explain(result.features)
        except Exception:
            logger.exception("SHAP explanation failed")
        explanation = fallback_text(result.decision, result.combined_score, reasons, result.rule_hits)
        alert = Alert(
            transaction_id=row.id, score=result.combined_score, decision=result.decision,
            reasons=reasons, explanation_text=explanation, explanation_source="shap_fallback",
        )
        db.add(alert)
        db.flush()
    db.commit()
    if alert and llm.is_enabled():
        background.add_task(explain_in_background, alert.id)

    return ScoreOut(
        transaction_id=row.id, decision=result.decision, combined_score=result.combined_score,
        xgb_proba=result.xgb_proba, anomaly_percentile=result.anomaly_percentile,
        similarity_score=result.similarity_score, fraud_neighbours=result.fraud_neighbours,
        rule_score=result.rule_score, rules=rules, alert_id=alert.id if alert else None,
        explanation=explanation, reasons=reasons,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )