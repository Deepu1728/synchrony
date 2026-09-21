import pytest

from app.models import Transaction
from app.schemas import TransactionIn
from app.scoring import features
from app.scoring.features import build_features

# M-prefixed ids never appear in the PaySim TRANSFER / CASH_OUT stream, so these accounts have no history.
SENDER, RECEIVER, OTHER = "M7770001", "M7770002", "M7770003"


def txn(**over) -> TransactionIn:
    base = dict(step=100, type="TRANSFER", amount=1000.0, name_orig=SENDER, oldbalance_org=5000.0,
                newbalance_orig=4000.0, name_dest=RECEIVER, oldbalance_dest=200.0, newbalance_dest=1200.0)
    return TransactionIn(**{**base, **over})


def add_history(db, step, amount, orig=SENDER, dest=RECEIVER):
    db.add(Transaction(
        step=step, type="TRANSFER", amount=amount, name_orig=orig, oldbalance_org=1e6, newbalance_orig=1e6 - amount,
        name_dest=dest, oldbalance_dest=0, newbalance_dest=amount, features={}, xgb_proba=0, anomaly_percentile=0,
        similarity_score=0, combined_score=0, decision="approve"))
    db.flush()


def test_copies_the_transaction_fields(db):
    f = build_features(db, txn())
    assert (f["amount"], f["oldbalanceOrg"], f["newbalanceOrig"]) == (1000.0, 5000.0, 4000.0)
    assert (f["oldbalanceDest"], f["newbalanceDest"]) == (200.0, 1200.0)
    assert f["is_transfer"] == 1
    assert build_features(db, txn(type="CASH_OUT"))["is_transfer"] == 0


@pytest.mark.parametrize("step,hour", [(1, 1), (23, 23), (24, 0), (25, 1), (100, 4), (743, 23)])
def test_hour_wraps_every_24_steps(db, step, hour):
    assert build_features(db, txn(step=step))["hour"] == hour


def test_balance_errors_are_zero_for_consistent_books(db):
    f = build_features(db, txn())
    assert f["error_balance_orig"] == 0
    assert f["error_balance_dest"] == 0


def test_balance_errors_show_missing_money(db):
    f = build_features(db, txn(newbalance_orig=4500.0, newbalance_dest=1000.0))
    assert f["error_balance_orig"] == 500.0
    assert f["error_balance_dest"] == 200.0


def test_drain_ratio_is_amount_over_old_balance(db):
    assert build_features(db, txn(amount=1000.0, oldbalance_org=4000.0))["balance_drain_ratio"] == 0.25
    full = build_features(db, txn(amount=4000.0, oldbalance_org=4000.0, newbalance_orig=0))
    assert full["balance_drain_ratio"] == 1.0 and full["orig_zero_balance"] == 0


def test_zero_sender_balance_does_not_divide_by_zero(db):
    f = build_features(db, txn(oldbalance_org=0.0, newbalance_orig=0.0))
    assert f["balance_drain_ratio"] == 0.0 and f["orig_zero_balance"] == 1


def test_drain_ratio_is_capped_at_10(db):
    assert build_features(db, txn(amount=100000.0, oldbalance_org=10.0))["balance_drain_ratio"] == 10.0


def test_unseen_accounts_have_neutral_history(db):
    f = build_features(db, txn())
    assert f["sender_prior_count"] == 0 and f["dest_prior_count"] == 0
    assert f["sender_time_gap"] == -1 and f["dest_time_gap"] == -1
    assert f["sender_velocity_24h"] == 0 and f["dest_velocity_24h"] == 0
    assert f["amount_vs_user_avg"] == 1.0 and f["dest_amount_vs_avg"] == 1.0
    assert f["new_recipient"] == 1 and f["dest_first_time"] == 1


def test_sender_history_features(db):
    add_history(db, step=90, amount=200.0, dest=OTHER)
    add_history(db, step=98, amount=400.0, dest=OTHER)
    f = build_features(db, txn(step=100, amount=1200.0))
    assert f["sender_prior_count"] == 2
    assert f["amount_vs_user_avg"] == 4.0            # 1200 / mean(200, 400)
    assert f["sender_time_gap"] == 2                 # last seen at step 98
    assert f["sender_velocity_24h"] == 2
    assert f["new_recipient"] == 1                   # sender never paid this receiver
    assert f["dest_first_time"] == 1                 # receiver never received anything


def test_receiver_history_features(db):
    add_history(db, step=95, amount=500.0, orig=OTHER)
    f = build_features(db, txn(step=100, amount=250.0))
    assert f["dest_prior_count"] == 1
    assert f["dest_amount_vs_avg"] == 0.5
    assert f["dest_time_gap"] == 5
    assert f["dest_velocity_24h"] == 1
    assert f["dest_first_time"] == 0
    assert f["new_recipient"] == 1                   # receiver known, but not to this sender


def test_known_pair_is_not_a_new_recipient(db):
    add_history(db, step=50, amount=300.0)
    f = build_features(db, txn(step=100))
    assert f["new_recipient"] == 0 and f["dest_first_time"] == 0


def test_velocity_window_includes_exactly_24_steps_back(db):
    add_history(db, step=76, amount=100.0)   # step - 24: inside the window
    add_history(db, step=75, amount=100.0)   # one step older: outside
    f = build_features(db, txn(step=100))
    assert f["sender_prior_count"] == 2
    assert f["sender_velocity_24h"] == 1


def test_history_ignores_the_future(db):
    add_history(db, step=150, amount=999.0)
    f = build_features(db, txn(step=100))
    assert f["sender_prior_count"] == 0 and f["new_recipient"] == 1


def test_same_step_history_counts_and_gap_is_zero(db):
    add_history(db, step=100, amount=100.0)
    f = build_features(db, txn(step=100))
    assert f["sender_prior_count"] == 1 and f["sender_time_gap"] == 0


def test_amount_ratio_is_capped_at_1000(db):
    add_history(db, step=90, amount=0.01, dest=OTHER)
    assert build_features(db, txn(amount=1e6))["amount_vs_user_avg"] == 1000.0


@pytest.mark.parametrize("amount,avg,expected", [(100, None, 1.0), (100, 0, 1.0), (100, -5, 1.0),
                                                 (100, 50, 2.0), (1e9, 1, 1000.0)])
def test_ratio_to_avg_helper(amount, avg, expected):
    assert features._ratio_to_avg(amount, avg) == expected


def test_all_21_model_inputs_are_present(db):
    assert len(build_features(db, txn())) == 21
