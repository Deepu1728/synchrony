from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FraudCase
from app.scoring import embedding


def fraud_neighbour_share(db: Session, features: dict) -> tuple[float, int]:
    vector = embedding.embed_one(features)
    db.execute(text("SET LOCAL hnsw.ef_search = 100"))
    labels = db.scalars(
        select(FraudCase.label)
        .order_by(FraudCase.embedding.l2_distance(vector))
        .limit(settings.similarity_k)
    ).all()
    if not labels:
        return 0.0, 0
    fraud = sum(1 for label in labels if label == "fraud")
    return fraud / len(labels), fraud