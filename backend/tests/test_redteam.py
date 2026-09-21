import random

import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.schemas import TransactionIn
from scripts import redteam


def fraud_rows(n=40, seed=3) -> list:
    rng = np.random.default_rng(seed)
    balance = rng.uniform(500_000, 5_000_000, n).round(2)
    return list(pd.DataFrame({
        "step": rng.integers(360, 700, n), "type": ["TRANSFER", "CASH_OUT"] * (n // 2),
        "amount": balance, "nameOrig": [f"C{1000000 + i}" for i in range(n)], "oldbalanceOrg": balance,
        "newbalanceOrig": 0.0, "nameDest": [f"C{2000000 + i}" for i in range(n)],
        "oldbalanceDest": 0.0, "newbalanceDest": 0.0, "isFraud": 1,
    }).itertuples(index=False))


@pytest.mark.parametrize("family", redteam.FAMILIES)
def test_every_family_produces_valid_consistent_scenarios(family):
    rng, ids = random.Random(1), redteam.IdFactory()
    seen = set()
    for row in fraud_rows(12):
        sc = redteam.make_scenario(family, row, rng, ids)
        assert sc.attack and all(t["true_label"] for t in sc.attack)
        assert all(t["true_label"] is False for t in sc.grooming)
        for t in sc.grooming + sc.attack:
            TransactionIn(**t)
            if family != "original":
                assert t["newbalance_orig"] == round(max(t["oldbalance_org"] - t["amount"], 0), 2)
        accounts = {t["name_orig"] for t in sc.attack} | {t["name_dest"] for t in sc.attack}
        assert not accounts & seen
        seen |= accounts


def test_structuring_stays_under_the_threshold_and_drains_the_account():
    rng, ids = random.Random(2), redteam.IdFactory()
    for row in fraud_rows(10):
        sc = redteam.make_scenario("structuring", row, rng, ids)
        amounts = [t["amount"] for t in sc.attack]
        assert len(amounts) >= 2 and max(amounts) < settings.rule_high_amount
        assert sum(amounts) <= row.oldbalanceOrg + 1 and len(amounts) <= redteam.MAX_PARTS
        assert [t["step"] for t in sc.attack] == list(range(int(row.step), int(row.step) + len(amounts)))
        assert len({t["name_orig"] for t in sc.attack}) == 1 and len({t["name_dest"] for t in sc.attack}) == 1
        balances = [t["oldbalance_org"] for t in sc.attack]
        assert balances[0] == row.oldbalanceOrg and balances == sorted(balances, reverse=True)


def test_variant_specific_properties():
    rng, ids = random.Random(4), redteam.IdFactory()
    for row in fraud_rows(10):
        partial = redteam.make_scenario("partial_drain", row, rng, ids).attack[0]
        assert 0.3 <= partial["amount"] / row.oldbalanceOrg <= 0.7
        assert 10 <= redteam.make_scenario("daytime", row, rng, ids).attack[0]["step"] % 24 <= 17
        aged = redteam.make_scenario("aged_mule", row, rng, ids)
        assert len(aged.grooming) == 4 and {g["name_dest"] for g in aged.grooming} == {aged.attack[0]["name_dest"]}
        assert max(g["step"] for g in aged.grooming) < aged.attack[0]["step"]
        combo = redteam.make_scenario("combo", row, rng, ids)
        assert 10 <= combo.attack[0]["step"] % 24 <= 17 and 0.3 <= combo.attack[0]["amount"] / row.oldbalanceOrg <= 0.7
    with pytest.raises(ValueError):
        redteam.make_scenario("nope", fraud_rows(2)[0], rng, ids)


def test_groomed_mule_balance_is_consistent_with_its_deposits():
    rng, ids = random.Random(6), redteam.IdFactory()
    for row in fraud_rows(6):
        sc = redteam.make_scenario("aged_mule", row, rng, ids)
        deposits = sum(g["amount"] for g in sc.grooming)
        assert sc.attack[0]["oldbalance_dest"] == pytest.approx(deposits, abs=0.05)
        for earlier, later in zip(sc.grooming, sc.grooming[1:]):
            assert later["oldbalance_dest"] == earlier["newbalance_dest"]


def test_account_ids_are_valid_and_never_reused():
    ids = redteam.IdFactory(start=5)
    issued = [ids.next(prefix) for prefix in ("99", "98", "97") * 50]
    assert len(set(issued)) == len(issued)
    for account in issued:
        TransactionIn(step=1, type="TRANSFER", amount=1, name_orig=account, oldbalance_org=1,
                      newbalance_orig=0, name_dest="C1", oldbalance_dest=0, newbalance_dest=1)


def test_scenarios_from_real_held_out_fraud_rows():
    if not redteam_data_available():
        pytest.skip("PaySim CSV not available locally")
    rows = redteam.real_fraud_rows(seed=7)[:30]
    rng, ids = random.Random(7), redteam.IdFactory()
    for family in redteam.FAMILIES:
        usable = [r for r in rows if family != "structuring" or r.oldbalanceOrg >= redteam.STRUCTURING_MIN_BALANCE]
        assert usable
        for row in usable[:5]:
            for t in (sc := redteam.make_scenario(family, row, rng, ids)).grooming + sc.attack:
                TransactionIn(**t)


def redteam_data_available() -> bool:
    from scripts import simulate

    return simulate.RAW.exists()