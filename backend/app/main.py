from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

app = FastAPI(title="Synchrony Fraud API", version="0.1.0")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unreachable")
    return {"status": "ok", "db": "ok"}