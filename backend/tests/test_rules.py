import pytest

from app.config import settings
from app.schemas import TransactionIn
from app.scoring.pipeline import decide
from app.scoring.rules import RuleHit, evaluate_rules, rule_score


def txn(**over) -> TransactionIn:
    base = dict(step=100, type="TRANSFER", amount=1000.0, name_orig="C1", oldbalance_org=5000.0,
                newbalance_orig=4000.0, name_dest="C2", oldbalance_dest=200.0, newbalance_dest=1200.0)
    return TransactionIn(**{**base, **over})


def codes(t: TransactionIn, hour: int = 14, dest_first_time: int = 0) -> list[str]:
    return [h.code for h in evaluate_rules(t, {"hour": hour, "dest_first_time": dest_first_time})]


def test_ordinary_transaction_triggers_nothing():
    assert codes(txn()) == []


# FULL_BALANCE_DRAIN: amount >= 99% of the sender's balance
@pytest.mark.parametrize("amount,fires", [(4950.0, True), (5000.0, True), (4949.99, False), (1000.0, False)])
def test_full_balance_drain_boundary(amount, fires):
    assert ("FULL_BALANCE_DRAIN" in codes(txn(amount=amount, oldbalance_org=5000.0))) is fires


def test_drain_rule_needs_a_positive_balance():
    assert "FULL_BALANCE_DRAIN" not in codes(txn(amount=100.0, oldbalance_org=0.0, newbalance_orig=0.0))


def test_drain_rule_weight_and_effect():
    hit = evaluate_rules(txn(amount=5000.0, newbalance_orig=0), {"hour": 14, "dest_first_time": 0})[0]
    assert hit.weight == 0.60 and not hit.forces_review and not hit.forces_block


# NIGHT_HOURS: hour <= 8, so hours 0..8 inclusive
@pytest.mark.parametrize("hour,fires", [(0, True), (3, True), (8, True), (9, False), (14, False), (23, False)])
def test_night_hours_boundary(hour, fires):
    assert ("NIGHT_HOURS" in codes(txn(), hour=hour)) is fires


def test_night_rule_follows_the_setting(monkeypatch):
    monkeypatch.setattr(settings, "rule_night_hour_end", 5)
    assert "NIGHT_HOURS" in codes(txn(), hour=5)
    assert "NIGHT_HOURS" not in codes(txn(), hour=6)


# NEW_RECEIVER_HIGH_AMOUNT: receiver never seen AND amount >= 200,000
@pytest.mark.parametrize("amount,first_time,fires", [
    (200_000.0, 1, True), (199_999.99, 1, False), (500_000.0, 1, True),
    (500_000.0, 0, False), (10.0, 1, False),
])
def test_new_receiver_high_amount(amount, first_time, fires):
    t = txn(amount=amount, oldbalance_org=amount * 3, newbalance_orig=amount * 2)
    assert ("NEW_RECEIVER_HIGH_AMOUNT" in codes(t, dest_first_time=first_time)) is fires


# AMOUNT_CAP: amount >= 10,000,000 forces a review
@pytest.mark.parametrize("amount,fires", [(10_000_000.0, True), (9_999_999.99, False), (50_000_000.0, True)])
def test_amount_cap_boundary_and_effect(amount, fires):
    hits = evaluate_rules(txn(amount=amount, oldbalance_org=amount * 2, newbalance_orig=amount),
                          {"hour": 14, "dest_first_time": 0})
    cap = [h for h in hits if h.code == "AMOUNT_CAP"]
    assert bool(cap) is fires
    if fires:
        assert cap[0].forces_review and not cap[0].forces_block


def test_drained_night_transfer_to_a_new_receiver_fires_every_rule_except_the_cap():
    t = txn(amount=300_000.0, oldbalance_org=300_000.0, newbalance_orig=0)
    assert codes(t, hour=3, dest_first_time=1) == ["FULL_BALANCE_DRAIN", "NIGHT_HOURS", "NEW_RECEIVER_HIGH_AMOUNT"]


def test_every_hit_has_a_message_and_a_valid_weight():
    t = txn(amount=20_000_000.0, oldbalance_org=20_000_000.0, newbalance_orig=0)
    hits = evaluate_rules(t, {"hour": 2, "dest_first_time": 1})
    assert {h.code for h in hits} == {"FULL_BALANCE_DRAIN", "NIGHT_HOURS", "NEW_RECEIVER_HIGH_AMOUNT", "AMOUNT_CAP"}
    assert all(h.message and 0 < h.weight < 1 for h in hits)


# rule_score combines hits as independent probabilities
def test_rule_score_of_nothing_is_zero():
    assert rule_score([]) == 0.0


def test_rule_score_of_one_hit_is_its_weight():
    assert rule_score([RuleHit("A", "a", 0.6)]) == pytest.approx(0.6)


def test_rule_score_combines_and_ignores_order():
    a, b, c = RuleHit("A", "a", 0.6), RuleHit("B", "b", 0.15), RuleHit("C", "c", 0.4)
    assert rule_score([a, b, c]) == pytest.approx(1 - 0.4 * 0.85 * 0.6)
    assert rule_score([c, a, b]) == pytest.approx(rule_score([a, b, c]))


def test_rule_score_never_reaches_one_with_partial_weights():
    hits = [RuleHit(str(i), "x", 0.6) for i in range(10)]
    assert rule_score(hits) < 1.0
    assert rule_score(hits) > rule_score(hits[:5])


# decide(): thresholds and forced flags
@pytest.mark.parametrize("score,review,block,expected", [
    (0.0, False, False, "approve"),
    (0.2999, False, False, "approve"),
    (0.30, False, False, "review"),
    (0.6999, False, False, "review"),
    (0.70, False, False, "block"),
    (0.0, True, False, "review"),
    (0.0, False, True, "block"),
    (0.5, False, True, "block"),
    (0.9, True, False, "block"),
])
def test_decide_with_forced_flags(score, review, block, expected):
    assert decide(score, forced_review=review, forced_block=block) == expected
