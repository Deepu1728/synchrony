from dataclasses import dataclass

from app.config import settings
from app.schemas import TransactionIn


@dataclass(frozen=True)
class RuleHit:
    code: str
    message: str
    weight: float
    forces_review: bool = False


def evaluate_rules(txn: TransactionIn, features: dict) -> list[RuleHit]:
    hits: list[RuleHit] = []

    if txn.oldbalance_org > 0 and txn.amount >= settings.rule_drain_ratio * txn.oldbalance_org:
        hits.append(RuleHit("FULL_BALANCE_DRAIN", "Sends the sender's entire balance", 0.60))

    if features["hour"] <= settings.rule_night_hour_end:
        hits.append(RuleHit("NIGHT_HOURS", "Made during night hours", 0.15))

    if features["dest_first_time"] and txn.amount >= settings.rule_high_amount:
        hits.append(RuleHit("NEW_RECEIVER_HIGH_AMOUNT", "High amount to a receiver never seen before", 0.40))

    if txn.amount >= settings.rule_amount_cap:
        hits.append(RuleHit("AMOUNT_CAP", "Amount exceeds the policy limit", 0.50, forces_review=True))

    return hits


def rule_score(hits: list[RuleHit]) -> float:
    remaining = 1.0
    for hit in hits:
        remaining *= 1.0 - hit.weight
    return 1.0 - remaining