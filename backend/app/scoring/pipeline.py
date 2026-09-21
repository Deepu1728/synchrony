from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import settings
from app.schemas import TransactionIn
from app.scoring import features as online_features
from app.scoring import ml, rules, similarity


@dataclass
class ScoreResult:
    features: dict
    rule_hits: list[rules.RuleHit] = field(default_factory=list)
    rule_score: float = 0.0
    xgb_proba: float = 0.0
    anomaly_percentile: float = 0.0
    similarity_score: float = 0.0
    fraud_neighbours: int = 0
    combined_score: float = 0.0
    decision: str = "approve"


def combine(xgb_p: float, anomaly: float, similar: float, rule: float) -> float:
    return (
        settings.score_weight_xgb * xgb_p
        + settings.score_weight_similarity * similar
        + settings.score_weight_rules * rule
        + settings.score_weight_anomaly * anomaly
    )


def decide(combined: float, forced_review: bool = False) -> str:
    if combined >= settings.block_threshold:
        return "block"
    if combined >= settings.review_threshold or forced_review:
        return "review"
    return "approve"


def score_transaction(db: Session, txn: TransactionIn) -> ScoreResult:
    feats = online_features.build_features(db, txn)
    hits = rules.evaluate_rules(txn, feats)
    rule = rules.rule_score(hits)
    xgb_p = ml.xgb_proba(feats)
    anomaly = ml.anomaly_percentile(feats)
    similar, fraud_neighbours = similarity.fraud_neighbour_share(db, feats)
    combined = combine(xgb_p, anomaly, similar, rule)
    return ScoreResult(
        features=feats,
        rule_hits=hits,
        rule_score=rule,
        xgb_proba=xgb_p,
        anomaly_percentile=anomaly,
        similarity_score=similar,
        fraud_neighbours=fraud_neighbours,
        combined_score=combined,
        decision=decide(combined, any(h.forces_review for h in hits)),
    )