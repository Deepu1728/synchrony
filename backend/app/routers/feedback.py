from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Alert, Feedback, FraudCase, User
from app.schemas import FeedbackIn, FeedbackOut
from app.scoring import embedding

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackOut, status_code=201)
def submit_feedback(body: FeedbackIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alert = db.get(Alert, body.alert_id, with_for_update=True)
    if not alert:
        raise HTTPException(404, "Alert not found")
    if alert.status != "open":
        raise HTTPException(409, "Alert already reviewed")

    txn = alert.transaction
    alert.status = "confirmed_fraud" if body.verdict == "fraud" else "false_positive"
    feedback = Feedback(alert_id=alert.id, user_id=user.id, verdict=body.verdict, note=body.note)
    db.add(feedback)
    db.add(FraudCase(
        embedding=embedding.embed_one(txn.features),
        label=body.verdict,
        source="feedback",
        transaction_id=txn.id,
        meta={"type": txn.type, "amount": round(txn.amount, 2), "hour": txn.step % 24},
    ))
    db.flush()
    db.commit()
    return FeedbackOut(id=feedback.id, alert_id=alert.id, verdict=feedback.verdict,
                       alert_status=alert.status, case_added=True)