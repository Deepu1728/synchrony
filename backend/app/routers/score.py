from fastapi import APIRouter

from app.schemas import TransactionIn

router = APIRouter(tags=["scoring"])


@router.post("/score")
def score(txn: TransactionIn):
    return {"validated": True, "note": "scoring pipeline not wired yet"}