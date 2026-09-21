from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alert, FraudCase, Transaction
from app.schemas import FeedOut, FeedRow, ReportFraudIn, ReportFraudOut
from app.scoring import embedding

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=FeedOut)
def list_transactions(
    after_id: int | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=500),
    decision: Literal["approve", "review", "block"] | None = None,
    db: Session = Depends(get_db),
):
    query = (
        select(Transaction, Alert.id.label("alert_id"), Alert.status.label("alert_status"))
        .outerjoin(Alert, Alert.transaction_id == Transaction.id)
    )
    if decision:
        query = query.where(Transaction.decision == decision)
    if after_id is None:
        rows = list(reversed(db.execute(query.order_by(Transaction.id.desc()).limit(limit)).all()))
    else:
        rows = db.execute(query.where(Transaction.id > after_id).order_by(Transaction.id).limit(limit)).all()
    items = [
        FeedRow(id=t.id, created_at=t.created_at, step=t.step, type=t.type, amount=t.amount,
                name_orig=t.name_orig, name_dest=t.name_dest, decision=t.decision, score=t.combined_score,
                alert_id=alert_id, alert_status=alert_status, true_label=t.true_label)
        for t, alert_id, alert_status in rows
    ]
    return FeedOut(items=items, last_id=items[-1].id if items else after_id)


@router.post("/{transaction_id}/report-fraud", response_model=ReportFraudOut, status_code=201)
def report_fraud(transaction_id: int, body: ReportFraudIn | None = None, db: Session = Depends(get_db)):
    txn = db.get(Transaction, transaction_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if db.scalar(select(Alert.id).where(Alert.transaction_id == transaction_id)):
        raise HTTPException(409, "Transaction already has an alert; review it with POST /feedback")
    if db.scalar(select(FraudCase.id).where(FraudCase.transaction_id == transaction_id, FraudCase.label == "fraud")):
        raise HTTPException(409, "Transaction already reported as fraud")

    case = FraudCase(
        embedding=embedding.embed_one(txn.features),
        label="fraud",
        source="reported",
        transaction_id=txn.id,
        meta={"type": txn.type, "amount": round(txn.amount, 2), "hour": txn.step % 24,
              "note": body.note if body else None},
    )
    db.add(case)
    db.flush()
    db.commit()
    return ReportFraudOut(transaction_id=txn.id, case_id=case.id, case_added=True)