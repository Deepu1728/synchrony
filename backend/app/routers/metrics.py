from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alert, FraudCase, Transaction
from app.schemas import AlertStats, DecisionCounts, GroundTruthMetrics, LearnedCases, MetricsOut

router = APIRouter(prefix="/metrics", tags=["metrics"])

NOTE = (
    "Catch rate and false-positive rate use the true_label recorded on simulator transactions. "
    "In production this ground truth would come from analyst confirmations and customer reports."
)


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


@router.get("", response_model=MetricsOut)
def metrics(window_minutes: int | None = Query(None, ge=1, le=525_600), db: Session = Depends(get_db)):
    t, a = Transaction, Alert
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes) if window_minutes else None

    txn_query = select(
        func.count(),
        func.count().filter(t.decision == "approve"),
        func.count().filter(t.decision == "review"),
        func.count().filter(t.decision == "block"),
        func.count().filter(t.true_label.is_(True)),
        func.count().filter(t.true_label.is_(True), t.decision != "approve"),
        func.count().filter(t.true_label.is_(True), t.decision == "block"),
        func.count().filter(t.true_label.is_(False)),
        func.count().filter(t.true_label.is_(False), t.decision != "approve"),
        func.count().filter(t.true_label.is_(False), t.decision == "block"),
    )
    alert_query = select(
        func.count().filter(a.status == "open"),
        func.count().filter(a.status == "confirmed_fraud"),
        func.count().filter(a.status == "false_positive"),
    )
    if cutoff:
        txn_query = txn_query.where(t.created_at >= cutoff)
        alert_query = alert_query.where(a.created_at >= cutoff)

    total, approve, review, block, fraud, fraud_flagged, fraud_blocked, genuine, genuine_flagged, genuine_blocked = (
        db.execute(txn_query).one()
    )
    open_alerts, confirmed, false_positive = db.execute(alert_query).one()
    learned_fraud, learned_legit = db.execute(
        select(
            func.count().filter(FraudCase.label == "fraud"),
            func.count().filter(FraudCase.label == "legit"),
        ).where(FraudCase.source.in_(["feedback", "reported"]))
    ).one()

    return MetricsOut(
        window_minutes=window_minutes,
        decisions=DecisionCounts(total=total, approve=approve, review=review, block=block),
        ground_truth=GroundTruthMetrics(
            labelled=fraud + genuine,
            fraud_total=fraud, fraud_flagged=fraud_flagged, fraud_blocked=fraud_blocked,
            genuine_total=genuine, genuine_flagged=genuine_flagged, genuine_blocked=genuine_blocked,
            catch_rate=ratio(fraud_flagged, fraud),
            block_catch_rate=ratio(fraud_blocked, fraud),
            false_positive_rate=ratio(genuine_flagged, genuine),
            false_block_rate=ratio(genuine_blocked, genuine),
            precision_flagged=ratio(fraud_flagged, fraud_flagged + genuine_flagged),
            precision_block=ratio(fraud_blocked, fraud_blocked + genuine_blocked),
            stream_fraud_share=ratio(fraud, fraud + genuine),
        ),
        alerts=AlertStats(
            open=open_alerts, confirmed_fraud=confirmed, false_positive=false_positive,
            reviewed=confirmed + false_positive, analyst_precision=ratio(confirmed, confirmed + false_positive),
        ),
        learned_cases=LearnedCases(fraud=learned_fraud, legit=learned_legit),
        note=NOTE,
    )