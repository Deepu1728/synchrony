from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_db
from app.explanations import improve_explanation
from app.models import Alert, Feedback, User
from app.schemas import (AlertList, AlertOut, FeedbackInfo, ScoreBreakdown, SimilarCase, SimilarOut,
                         SimilarSummary, Thresholds, TransactionSummary)
from app.scoring import similarity

router = APIRouter(prefix="/alerts", tags=["alerts"])


def to_out(alert: Alert, feedback: FeedbackInfo | None = None) -> AlertOut:
    txn = alert.transaction
    return AlertOut(
        id=alert.id, decision=alert.decision, score=alert.score, status=alert.status,
        reasons=alert.reasons, rules=txn.rule_flags,
        explanation_text=alert.explanation_text, explanation_source=alert.explanation_source,
        created_at=alert.created_at, transaction=TransactionSummary.model_validate(txn),
        scores=ScoreBreakdown(model=txn.xgb_proba, similarity=txn.similarity_score,
                              anomaly=txn.anomaly_percentile, rules=txn.rule_score, combined=txn.combined_score),
        thresholds=Thresholds(review=settings.review_threshold, block=settings.block_threshold),
        feedback=feedback,
    )


def latest_feedback(db: Session, alert_id: int) -> FeedbackInfo | None:
    row = db.execute(
        select(Feedback.verdict, Feedback.note, Feedback.created_at, User.username)
        .join(User, User.id == Feedback.user_id)
        .where(Feedback.alert_id == alert_id)
        .order_by(Feedback.id.desc())
        .limit(1)
    ).first()
    return FeedbackInfo(verdict=row.verdict, username=row.username, note=row.note, created_at=row.created_at) if row else None


@router.get("", response_model=AlertList)
def list_alerts(
    status_filter: Literal["open", "confirmed_fraud", "false_positive"] | None = Query(None, alias="status"),
    decision: Literal["review", "block"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Alert)
    if status_filter:
        query = query.where(Alert.status == status_filter)
    if decision:
        query = query.where(Alert.decision == decision)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.options(joinedload(Alert.transaction)).order_by(Alert.id.desc()).limit(limit).offset(offset)
    ).all()
    return AlertList(total=total, items=[to_out(a) for a in rows])


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id, options=[joinedload(Alert.transaction)])
    if not alert:
        raise HTTPException(404, "Alert not found")
    return to_out(alert, latest_feedback(db, alert.id))


@router.get("/{alert_id}/similar", response_model=SimilarOut)
def similar_cases(alert_id: int, k: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id, options=[joinedload(Alert.transaction)])
    if not alert:
        raise HTTPException(404, "Alert not found")
    cases = similarity.nearest_cases(db, alert.transaction.features, k=k,
                                     exclude_transaction_id=alert.transaction_id)
    linked = {}
    txn_ids = [c.transaction_id for c in cases if c.transaction_id]
    if txn_ids:
        linked = dict(db.execute(select(Alert.transaction_id, Alert.id).where(Alert.transaction_id.in_(txn_ids))).all())
    counts = similarity.summarize(cases)
    return SimilarOut(
        alert_id=alert.id, k=k,
        cases=[
            SimilarCase(id=c.id, label=c.label, source=c.source, distance=round(c.distance, 4),
                        type=c.meta.get("type"), amount=c.meta.get("amount"), hour=c.meta.get("hour"),
                        note=c.meta.get("note"), alert_id=linked.get(c.transaction_id))
            for c in cases
        ],
        summary=SimilarSummary(fraud=counts.fraud, legit=len(cases) - counts.fraud,
                               learned_fraud=counts.learned_fraud, learned_legit=counts.learned_legit),
    )


@router.post("/{alert_id}/explain", response_model=AlertOut)
def explain_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id, options=[joinedload(Alert.transaction)])
    if not alert:
        raise HTTPException(404, "Alert not found")
    improve_explanation(db, alert)
    return to_out(alert, latest_feedback(db, alert.id))