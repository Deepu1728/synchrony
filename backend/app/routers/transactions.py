from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alert, FraudCase, Transaction
from app.schemas import ReportFraudIn, ReportFraudOut
from app.scoring import embedding

router = APIRouter(prefix="/transactions", tags=["transactions"])


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