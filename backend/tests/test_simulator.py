import time

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Alert
from app.schemas import TransactionIn
from scripts import simulate


def make_rows(n_genuine: int, n_fraud: int = 0) -> pd.DataFrame:
    rows = []
    for i in range(n_genuine):
        rows.append(dict(step=14, type="CASH_OUT", amount=8500.0, nameOrig=f"C{1000000 + i}",
                         oldbalanceOrg=20632.0, newbalanceOrig=12132.0, nameDest=f"C{2000000 + i}",
                         oldbalanceDest=21182.0, newbalanceDest=29682.0, isFraud=0))
    for i in range(n_fraud):
        rows.append(dict(step=4, type="TRANSFER", amount=692654.27, nameOrig=f"C{3000000 + i}",
                         oldbalanceOrg=692654.27, newbalanceOrig=0.0, nameDest=f"C{4000000 + i}",
                         oldbalanceDest=0.0, newbalanceDest=0.0, isFraud=1))
    return pd.DataFrame(rows)


@pytest.fixture
def logged_in(client, auth):
    client.headers.update(auth)
    return client


def test_payload_matches_api_schema():
    row = next(make_rows(1, 0).itertuples(index=False))
    payload = simulate.to_payload(row)
    txn = TransactionIn(**payload)
    assert txn.true_label is False and txn.name_orig == "C1000000"


def test_load_stream_filters_sorts_and_keeps_last_fifth(tmp_path):
    rng = np.random.default_rng(0)
    modeled = make_rows(100).assign(step=rng.integers(1, 50, 100))
    other = make_rows(20).assign(type="PAYMENT")
    csv = tmp_path / "paysim.csv"
    pd.concat([modeled, other]).sample(frac=1, random_state=1).assign(isFlaggedFraud=0).to_csv(csv, index=False)
    stream = simulate.load_stream(csv, test_fraction=0.8)
    expected = modeled.sort_values("step", kind="stable").iloc[80:]
    assert len(stream) == 20 and set(stream.type) == {"CASH_OUT"}
    assert stream.step.is_monotonic_increasing
    assert list(stream.step) == list(expected.step)


def test_pick_natural_and_fraud_share():
    stream = pd.concat([make_rows(1960), make_rows(0, 40)]).reset_index(drop=True)
    stream = stream.sample(frac=1, random_state=3).reset_index(drop=True)
    natural = simulate.pick(stream, 0, 100, None)
    assert len(natural) == 100 and natural.index.is_monotonic_increasing

    mixed = simulate.pick(stream, 0, 100, 0.10)
    assert len(mixed) == 100 and int(mixed.isFraud.sum()) == 10
    assert mixed.index.is_monotonic_increasing
    assert simulate.pick(stream, 0, 100, 0.10).index.equals(mixed.index)

    no_fraud = simulate.pick(make_rows(50), 0, 20, 0.10)
    assert len(no_fraud) == 20 and no_fraud.isFraud.sum() == 0


def test_stats_summary_math():
    s = simulate.Stats()
    for is_fraud, decision in [(True, "block"), (True, "block"), (True, "review"), (True, "approve"),
                               (False, "approve"), (False, "approve"), (False, "review"), (False, "block")]:
        s.record(is_fraud, decision, 20.0, 15.0)
    r = s.summary(elapsed=4.0)
    assert r["sent"] == 8 and r["throughput_tps"] == 2.0
    assert r["fraud"] == {"total": 4, "blocked": 2, "review": 1, "missed": 1}
    assert r["genuine"] == {"total": 4, "blocked": 1, "review": 1, "approved": 2}
    assert r["recall_block"] == 0.5 and r["recall_flagged"] == 0.75
    assert r["precision_block"] == pytest.approx(0.6667, abs=1e-4)
    assert r["precision_flagged"] == pytest.approx(0.6, abs=1e-4)
    assert r["latency_ms"]["client_p50"] == 20.0


def test_empty_stats_do_not_divide_by_zero():
    r = simulate.Stats().summary(elapsed=0.0)
    assert r["sent"] == 0 and r["recall_block"] is None and r["precision_block"] is None
    assert r["latency_ms"]["client_p50"] is None


def test_login_helper(client):
    if not settings.seed_admin_password:
        pytest.skip("needs SEED_ADMIN_PASSWORD")
    assert simulate.login(client, "admin", settings.seed_admin_password)
    with pytest.raises(simulate.SimulationAborted):
        simulate.login(client, "admin", "wrong-password")


def test_replay_end_to_end_with_feedback(logged_in, db):
    rows = pd.concat([make_rows(5, 0), make_rows(0, 1)]).reset_index(drop=True)
    lines = []
    stats = simulate.replay(logged_in, rows, feedback=1.0, out=lines.append)
    assert stats.fraud["block"] == 1 and stats.fraud["approve"] == 0
    assert stats.genuine["approve"] == 5
    assert stats.feedback == {"fraud_201": 1}
    alert = db.scalars(select(Alert).order_by(Alert.id.desc()).limit(1)).one()
    assert alert.status == "confirmed_fraud"
    summary = stats.summary(1.0)
    assert summary["recall_block"] == 1.0 and summary["precision_block"] == 1.0


def test_replay_counts_validation_rejections(logged_in):
    rows = make_rows(2).assign(amount=[-5.0, 8500.0])
    lines = []
    stats = simulate.replay(logged_in, rows, out=lines.append)
    assert stats.errors == {"rejected": 1} and sum(stats.genuine.values()) == 1
    assert any("rejected by validation" in line for line in lines)


def test_replay_stops_at_deadline(logged_in):
    stats = simulate.replay(logged_in, make_rows(5), deadline=time.perf_counter() - 1, out=lambda *_: None)
    assert stats.summary(1.0)["sent"] == 0


def test_replay_relogs_in_after_401(client, auth):
    client.headers["Authorization"] = "Bearer expired.token.value"
    calls = []

    def relogin():
        calls.append(1)
        client.headers.update(auth)

    stats = simulate.replay(client, make_rows(2), relogin=relogin, out=lambda *_: None)
    assert calls and sum(stats.genuine.values()) == 2