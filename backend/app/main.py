import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.routers import alerts, auth, feedback, metrics, score, transactions
from app.scoring import ml


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=ml.warmup, daemon=True).start()
    yield


app = FastAPI(title="Synchrony Fraud API", version="0.1.0", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Drop the echoed input: NaN / Infinity cannot be encoded as JSON and used to turn a 422 into a 500.
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


protected = [Depends(get_current_user)]
app.include_router(auth.router)
app.include_router(score.router, dependencies=protected)
app.include_router(alerts.router, dependencies=protected)
app.include_router(feedback.router, dependencies=protected)
app.include_router(transactions.router, dependencies=protected)
app.include_router(metrics.router, dependencies=protected)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unreachable")
    return {"status": "ok", "db": "ok"}