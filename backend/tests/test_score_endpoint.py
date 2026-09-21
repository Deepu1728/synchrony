import pytest
from sqlalchemy import func, select

from app import llm
from app.config import settings
from app.models import Alert, Transaction
from app.routers import score as score_router
from app.scoring import ml

APPROVE = {
    "step": 14, "type": "CASH_OUT", "amount": 8500, "name_orig": "M7772001", "oldbalance_org": 20632,
    "newbalance_orig": 12132, "name_dest": "M7772002", "oldbalance_dest": 21182, "newbalance_dest": 29682,
}
REVIEW = {**APPROVE, "amount": 12_000_000, "oldbalance_org": 30_000_000, "newbalance_orig": 18_000_000}
BLOCK = {
    "step": 4, "type": "TRANSFER", "amount": 692654.27, "name_orig": "M7772003", "oldbalance_org": 692654.27,
    "newbalance_orig": 0, "name_dest": "M7772004", "oldbalance_dest": 0, "newbalance_dest": 0,
}
RESPONSE_FIELDS = {
    "transaction_id", "decision", "combined_score", "xgb_proba", "anomaly_percentile", "similarity_score",
    "fraud_neighbours", "rule_score", "rules", "alert_id", "explanation", "reasons", "latency_ms",
}


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def post(client, auth, payload):
    return client.post("/score", json=payload, headers=auth)


# --- decisions --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("payload,decision", [(APPROVE, "approve"), (REVIEW, "review"), (BLOCK, "block")])
def test_each_decision_is_reachable(client, auth, payload, decision):
    r = post(client, auth, payload)
    assert r.status_code == 200 and r.json()["decision"] == decision


def test_response_has_every_documented_field(client, auth):
    body = post(client, auth, BLOCK).json()
    assert set(body) == RESPONSE_FIELDS
    for name in ("combined_score", "xgb_proba", "anomaly_percentile", "similarity_score", "rule_score"):
        assert 0.0 <= body[name] <= 1.0
    assert isinstance(body["fraud_neighbours"], int) and body["latency_ms"] > 0


def test_combined_score_matches_the_decision_thresholds(client, auth):
    for payload, decision in [(APPROVE, "approve"), (BLOCK, "block")]:
        body = post(client, auth, payload).json()
        if decision == "approve":
            assert body["combined_score"] < settings.review_threshold
        else:
            assert body["combined_score"] >= settings.block_threshold


def test_review_comes_from_the_amount_cap_rule(client, auth):
    body = post(client, auth, REVIEW).json()
    assert "AMOUNT_CAP" in {r["code"] for r in body["rules"]}
    assert settings.review_threshold <= body["combined_score"] < settings.block_threshold


# --- what gets stored -------------------------------------------------------------------------------------------

def test_every_scored_transaction_is_stored_with_its_scores(client, auth, db):
    body = post(client, auth, APPROVE).json()
    row = db.get(Transaction, body["transaction_id"])
    assert row.decision == "approve" and row.combined_score == body["combined_score"]
    assert row.name_orig == APPROVE["name_orig"] and row.amount == APPROVE["amount"]
    assert len(row.features) == 21 and row.rule_flags == body["rules"]


def test_true_label_is_stored_only_when_supplied(client, auth, db):
    plain = post(client, auth, APPROVE).json()
    labelled = post(client, auth, {**BLOCK, "true_label": True}).json()
    assert db.get(Transaction, plain["transaction_id"]).true_label is None
    assert db.get(Transaction, labelled["transaction_id"]).true_label is True


@pytest.mark.parametrize("payload,expect_alert", [(APPROVE, False), (REVIEW, True), (BLOCK, True)])
def test_alert_exists_only_for_review_and_block(client, auth, db, payload, expect_alert):
    before = count(db, Alert)
    body = post(client, auth, payload).json()
    assert count(db, Alert) == before + (1 if expect_alert else 0)
    assert (body["alert_id"] is not None) is expect_alert
    assert (body["explanation"] is not None) is expect_alert


def test_alert_copies_score_decision_and_starts_open(client, auth, db):
    body = post(client, auth, BLOCK).json()
    alert = db.get(Alert, body["alert_id"])
    assert alert.transaction_id == body["transaction_id"] and alert.decision == "block"
    assert alert.score == body["combined_score"] and alert.status == "open"
    assert alert.explanation_source == "shap_fallback" and alert.explanation_text == body["explanation"]
    assert len(alert.reasons) == 6


def test_explanation_names_the_decision_and_the_rules(client, auth):
    body = post(client, auth, BLOCK).json()
    assert body["explanation"].startswith("Blocked")
    assert "entire balance" in body["explanation"]


# --- explanation failures and the LLM ---------------------------------------------------------------------------

def test_shap_failure_still_scores_and_creates_the_alert(client, auth, db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("shap unavailable")
    monkeypatch.setattr(ml, "explain", boom)
    r = post(client, auth, BLOCK)
    body = r.json()
    assert r.status_code == 200 and body["decision"] == "block" and body["reasons"] == []
    assert db.get(Alert, body["alert_id"]).reasons == []
    assert body["explanation"].startswith("Blocked")


def test_llm_rewrite_is_queued_only_for_alerts_and_only_when_enabled(client, auth, monkeypatch):
    queued = []
    monkeypatch.setattr(score_router, "explain_in_background", lambda alert_id: queued.append(alert_id))
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    post(client, auth, APPROVE)
    assert queued == []
    body = post(client, auth, BLOCK).json()
    assert queued == [body["alert_id"]]


def test_no_llm_rewrite_is_queued_when_disabled(client, auth, monkeypatch):
    queued = []
    monkeypatch.setattr(score_router, "explain_in_background", lambda alert_id: queued.append(alert_id))
    monkeypatch.setattr(llm, "is_enabled", lambda: False)
    post(client, auth, BLOCK)
    assert queued == []


# --- validation -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("change", [
    {"type": "PAYMENT"},
    {"type": "transfer"},
    {"amount": -1},
    {"amount": 2e11},
    {"oldbalance_org": -5},
    {"step": 0},
    {"step": 100_001},
    {"name_orig": "X123"},
    {"name_dest": "C12345678901234"},
    {"name_orig": "C1", "name_dest": "C1"},
    {"unexpected": "field"},
    {"amount": "lots"},
])
def test_invalid_payloads_are_rejected_and_nothing_is_stored(client, auth, db, change):
    before = count(db, Transaction)
    r = post(client, auth, {**APPROVE, **change})
    assert r.status_code == 422
    assert count(db, Transaction) == before


@pytest.mark.parametrize("missing", ["step", "type", "amount", "name_orig", "name_dest", "newbalance_dest"])
def test_missing_fields_are_rejected(client, auth, missing):
    payload = {k: v for k, v in APPROVE.items() if k != missing}
    assert post(client, auth, payload).status_code == 422


def test_nan_and_infinity_are_rejected(client, auth):
    for bad in ("NaN", "Infinity"):
        body = '{"step":1,"type":"TRANSFER","amount":%s,"name_orig":"C1","oldbalance_org":1,' \
               '"newbalance_orig":0,"name_dest":"C2","oldbalance_dest":0,"newbalance_dest":0}' % bad
        r = client.post("/score", content=body, headers={**auth, "Content-Type": "application/json"})
        assert r.status_code == 422


def test_score_requires_a_valid_token(client, auth):
    assert client.post("/score", json=APPROVE).status_code == 401
    assert client.post("/score", json=APPROVE, headers={"Authorization": "Bearer nonsense"}).status_code == 401


# --- preview ----------------------------------------------------------------------------------------------------

def test_preview_scores_without_storing_anything(client, auth, db):
    txns, alerts = count(db, Transaction), count(db, Alert)
    body = client.post("/score/preview", json=BLOCK, headers=auth).json()
    assert body["decision"] == "block" and {r["code"] for r in body["rules"]} >= {"FULL_BALANCE_DRAIN"}
    assert set(body) == {"decision", "combined_score", "xgb_proba", "similarity_score", "rules"}
    assert count(db, Transaction) == txns and count(db, Alert) == alerts


def test_preview_agrees_with_score(client, auth):
    preview = client.post("/score/preview", json=REVIEW, headers=auth).json()
    scored = post(client, auth, REVIEW).json()
    assert preview["decision"] == scored["decision"]
    assert preview["combined_score"] == pytest.approx(scored["combined_score"])


def test_preview_requires_a_token(client):
    assert client.post("/score/preview", json=APPROVE).status_code == 401
