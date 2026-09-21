from dataclasses import dataclass, field

from sqlalchemy import or_, select, text
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


@dataclass(frozen=True)
class Case:
    id: int
    label: str
    source: str
    distance: float
    transaction_id: int | None
    meta: dict = field(default_factory=dict)


def nearest_cases(db: Session, features: dict, k: int | None = None,
                  exclude_transaction_id: int | None = None) -> list[Case]:
    vector = embedding.embed_one(features)
    if settings.similarity_exact:
        db.execute(text("SET LOCAL enable_indexscan = off"))
        db.execute(text("SET LOCAL enable_bitmapscan = off"))
    else:
        db.execute(text("SET LOCAL hnsw.ef_search = 200"))
    distance = FraudCase.embedding.l2_distance(vector)
    query = select(FraudCase.id, FraudCase.label, FraudCase.source, distance.label("distance"),
                   FraudCase.transaction_id, FraudCase.meta)
    if exclude_transaction_id is not None:
        query = query.where(or_(FraudCase.transaction_id.is_(None),
                                FraudCase.transaction_id != exclude_transaction_id))
    try:
        rows = db.execute(query.order_by(distance).limit(k or settings.similarity_k)).all()
    finally:
        if settings.similarity_exact:
            db.execute(text("SET LOCAL enable_indexscan = on"))
            db.execute(text("SET LOCAL enable_bitmapscan = on"))
    return [Case(r.id, r.label, r.source, float(r.distance), r.transaction_id, r.meta or {}) for r in rows]


def summarize(cases: list[Case]) -> Neighbours:
    if not cases:
        return Neighbours()
    fraud = sum(1 for c in cases if c.label == "fraud")
    return Neighbours(
        fraud_share=fraud / len(cases),
        fraud=fraud,
        learned_fraud=sum(1 for c in cases if c.label == "fraud" and c.source in LEARNED_SOURCES),
        learned_legit=sum(1 for c in cases if c.label == "legit" and c.source in LEARNED_SOURCES),
    )


def find_neighbours(db: Session, features: dict) -> Neighbours:
    return summarize(nearest_cases(db, features))