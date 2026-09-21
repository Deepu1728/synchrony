from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FraudCase
from app.scoring import embedding

LEARNED_SOURCES = ("feedback", "reported")


@dataclass(frozen=True)
class Neighbours:
    fraud_share: float = 0.0
    fraud: int = 0
    learned_fraud: int = 0
    learned_legit: int = 0


def find_neighbours(db: Session, features: dict) -> Neighbours:
    vector = embedding.embed_one(features)
    if settings.similarity_exact:
        db.execute(text("SET LOCAL enable_indexscan = off"))
        db.execute(text("SET LOCAL enable_bitmapscan = off"))
    else:
        db.execute(text("SET LOCAL hnsw.ef_search = 200"))
    try:
        rows = db.execute(
            select(FraudCase.label, FraudCase.source)
            .order_by(FraudCase.embedding.l2_distance(vector))
            .limit(settings.similarity_k)
        ).all()
    finally:
        if settings.similarity_exact:
            db.execute(text("SET LOCAL enable_indexscan = on"))
            db.execute(text("SET LOCAL enable_bitmapscan = on"))
    if not rows:
        return Neighbours()
    fraud = sum(1 for label, _ in rows if label == "fraud")
    return Neighbours(
        fraud_share=fraud / len(rows),
        fraud=fraud,
        learned_fraud=sum(1 for label, src in rows if label == "fraud" and src in LEARNED_SOURCES),
        learned_legit=sum(1 for label, src in rows if label == "legit" and src in LEARNED_SOURCES),
    )