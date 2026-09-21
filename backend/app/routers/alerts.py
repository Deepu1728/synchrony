from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.explanations import improve_explanation
from app.models import Alert
from app.schemas import AlertList, AlertOut, TransactionSummary

router = APIRouter(prefix="/alerts", tags=["alerts"])


def to_out(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id, decision=alert.decision, score=alert.score, status=alert.status,
        reasons=alert.reasons, rules=alert.transaction.rule_flags,
        explanation_text=alert.explanation_text, explanation_source=alert.explanation_source,
        created_at=alert.created_at, transaction=TransactionSummary.model_validate(alert.transaction),
    )


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
    return to_out(alert)

@router.post("/{alert_id}/explain", response_model=AlertOut)
def explain_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id, options=[joinedload(Alert.transaction)])
    if not alert:
        raise HTTPException(404, "Alert not found")
    improve_explanation(db, alert)
    return to_out(alert)