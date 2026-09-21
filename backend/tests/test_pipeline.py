import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.schemas import TransactionIn
from app.scoring import rules
from app.scoring.pipeline import combine, decide, score_transaction

FRAUD = TransactionIn(
    step=4, type="TRANSFER", amount=692654.27,
    name_orig="C1231006815", oldbalance_org=692654.27, newbalance_orig=0,
    name_dest="C553264065", oldbalance_dest=0, newbalance_dest=0,
)
GENUINE = TransactionIn(
    step=14, type="CASH_OUT", amount=8500,
    name_orig="C840083671", oldbalance_org=20632, newbalance_orig=12132,
    name_dest="C38997010", oldbalance_dest=21182, newbalance_dest=29682,
)


@pytest.fixture
def db():
    session = Session(engine)
    yield session
    session.rollback()
    session.close()


def test_fraud_is_blocked(db):
    r = score_transaction(db, FRAUD)
    assert r.decision == "block"
    assert r.xgb_proba > 0.5
    assert r.similarity_score >= 0.7
    assert {h.code for h in r.rule_hits} >= {"FULL_BALANCE_DRAIN", "NIGHT_HOURS"}


def test_genuine_is_approved(db):
    r = score_transaction(db, GENUINE)
    assert r.decision == "approve"
    assert r.combined_score < settings.review_threshold
    assert r.rule_hits == []


def test_amount_cap_forces_review(db):
    big = GENUINE.model_copy(update={
        "amount": 12_000_000, "oldbalance_org": 30_000_000, "newbalance_orig": 18_000_000,
    })
    r = score_transaction(db, big)
    assert "AMOUNT_CAP" in {h.code for h in r.rule_hits}
    assert r.decision in ("review", "block")


def test_decide_thresholds():
    assert decide(settings.review_threshold - 0.01) == "approve"
    assert decide(settings.review_threshold) == "review"
    assert decide(settings.block_threshold) == "block"
    assert decide(0.0, forced_review=True) == "review"
    assert decide(1.0, forced_review=True) == "block"


def test_combine_uses_configured_weights():
    assert combine(1, 0, 0, 0) == pytest.approx(settings.score_weight_xgb)
    assert combine(0, 0, 1, 0) == pytest.approx(settings.score_weight_similarity)
    total = (settings.score_weight_xgb + settings.score_weight_similarity
             + settings.score_weight_rules + settings.score_weight_anomaly)
    assert combine(1, 1, 1, 1) == pytest.approx(total)


def test_rule_score_is_independent_or():
    hits = [rules.RuleHit("A", "a", 0.5), rules.RuleHit("B", "b", 0.5)]
    assert rules.rule_score(hits) == pytest.approx(0.75)
    assert rules.rule_score([]) == 0.0