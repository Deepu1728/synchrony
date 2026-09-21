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


def decide(combined: float, forced_review: bool = False, forced_block: bool = False) -> str:
    if combined >= settings.block_threshold or forced_block:
        return "block"
    if combined >= settings.review_threshold or forced_review:
        return "review"
    return "approve"


def learned_pattern_hit(n: similarity.Neighbours) -> rules.RuleHit | None:
    evidence = n.learned_fraud - n.learned_legit
    if evidence >= settings.learned_review_min:
        return rules.RuleHit(
            "LEARNED_FRAUD_PATTERN",
            f"Closely matches {n.learned_fraud} analyst-confirmed fraud cases",
            0.5,
            forces_review=True,
            forces_block=evidence >= settings.learned_block_min,
        )
    return None


def score_transaction(db: Session, txn: TransactionIn) -> ScoreResult:
    feats = online_features.build_features(db, txn)
    hits = rules.evaluate_rules(txn, feats)
    xgb_p = ml.xgb_proba(feats)
    anomaly = ml.anomaly_percentile(feats)
    neighbours = similarity.find_neighbours(db, feats)
    similar, fraud_neighbours = neighbours.fraud_share, neighbours.fraud
    if learned := learned_pattern_hit(neighbours):
        hits.append(learned)
    rule = rules.rule_score(hits)
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
        decision=decide(combined, any(h.forces_review for h in hits), any(h.forces_block for h in hits)),
    )