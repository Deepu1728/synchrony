import pytest
from sqlalchemy import func, select

from app.models import FraudCase, Transaction
from app.scoring import embedding
from app.scoring.pipeline import decide, learned_pattern_hit
from app.scoring.similarity import Neighbours

BENIGN = {
    "step": 14, "type": "CASH_OUT", "amount": 8500, "oldbalance_org": 20632, "newbalance_orig": 12132,
    "oldbalance_dest": 21182, "newbalance_dest": 29682,
}
FRAUD = {
    "step": 4, "type": "TRANSFER", "amount": 692654.27, "name_orig": "C1231006815",
    "oldbalance_org": 692654.27, "newbalance_orig": 0, "name_dest": "C553264065",
    "oldbalance_dest": 0, "newbalance_dest": 0,
}


def benign(i: int) -> dict:
    return {**BENIGN, "name_orig": f"C{5000000 + i}", "name_dest": f"C{6000000 + i}"}


def score(client, auth, payload) -> dict:
    r = client.post("/score", json=payload, headers=auth)
    assert r.status_code == 200
    return r.json()


def report(client, auth, transaction_id, **kwargs):
    return client.post(f"/transactions/{transaction_id}/report-fraud", json=kwargs, headers=auth)


def label_fraud(client, auth, body):
    if body["alert_id"]:
        r = client.post("/feedback", json={"alert_id": body["alert_id"], "verdict": "fraud"}, headers=auth)
    else:
        r = report(client, auth, body["transaction_id"])
    assert r.status_code == 201


def codes(body) -> set:
    return {r["code"] for r in body["rules"]}


def test_report_fraud_adds_a_learned_case(client, auth, db):
    body = score(client, auth, benign(1))
    assert body["decision"] == "approve" and body["alert_id"] is None
    r = report(client, auth, body["transaction_id"], note="customer dispute")
    assert r.status_code == 201 and r.json()["case_added"] is True
    case = db.get(FraudCase, r.json()["case_id"])
    assert case.label == "fraud" and case.source == "reported" and case.transaction_id == body["transaction_id"]
    assert case.meta["note"] == "customer dispute"


def test_report_fraud_rejects_duplicates_alerts_and_bad_input(client, auth):
    body = score(client, auth, benign(2))
    assert report(client, auth, body["transaction_id"]).status_code == 201
    assert report(client, auth, body["transaction_id"]).status_code == 409

    flagged = score(client, auth, FRAUD)
    assert flagged["alert_id"]
    assert report(client, auth, flagged["transaction_id"]).status_code == 409

    assert report(client, auth, 99999999).status_code == 404
    assert report(client, auth, body["transaction_id"], note="x" * 501).status_code == 422
    assert client.post(f"/transactions/{body['transaction_id']}/report-fraud").status_code == 401


def test_three_learned_cases_force_review_of_a_matching_transaction(client, auth):
    assert "LEARNED_FRAUD_PATTERN" not in codes(score(client, auth, benign(10)))
    for i in (11, 12, 13):
        assert report(client, auth, score(client, auth, benign(i))["transaction_id"]).status_code == 201
    body = score(client, auth, benign(14))
    assert "LEARNED_FRAUD_PATTERN" in codes(body) and body["decision"] == "review"
    assert "analyst-confirmed" in body["explanation"]


def test_five_learned_cases_block_a_matching_transaction(client, auth):
    for i in range(20, 25):
        label_fraud(client, auth, score(client, auth, benign(i)))
    body = score(client, auth, benign(26))
    assert "LEARNED_FRAUD_PATTERN" in codes(body) and body["decision"] == "block"


def test_learned_legit_cases_outweigh_and_prevent_the_rule(client, auth, db):
    first = score(client, auth, benign(30))
    for i in (31, 32, 33):
        assert report(client, auth, score(client, auth, benign(i))["transaction_id"]).status_code == 201
    vector = embedding.embed_one(db.get(Transaction, first["transaction_id"]).features)
    for _ in range(3):
        db.add(FraudCase(embedding=vector, label="legit", source="feedback", meta={}))
    db.flush()
    assert "LEARNED_FRAUD_PATTERN" not in codes(score(client, auth, benign(34)))


def test_clearing_a_false_alarm_stops_the_rule_for_similar_transactions(client, auth):
    for i in (40, 41, 42):
        assert report(client, auth, score(client, auth, benign(i))["transaction_id"]).status_code == 201
    flagged = score(client, auth, benign(43))
    assert flagged["decision"] == "review" and flagged["alert_id"]
    r = client.post("/feedback", json={"alert_id": flagged["alert_id"], "verdict": "legit"}, headers=auth)
    assert r.status_code == 201 and r.json()["alert_status"] == "false_positive"
    healed = score(client, auth, benign(44))
    assert healed["decision"] == "approve" and "LEARNED_FRAUD_PATTERN" not in codes(healed)


def test_preview_scores_without_saving_anything(client, auth, db):
    from app.models import Alert

    txns, alerts = (db.scalar(select(func.count()).select_from(m)) for m in (Transaction, Alert))
    r = client.post("/score/preview", json=FRAUD, headers=auth)
    assert r.status_code == 200 and r.json()["decision"] == "block"
    assert {x["code"] for x in r.json()["rules"]} >= {"FULL_BALANCE_DRAIN"}
    assert db.scalar(select(func.count()).select_from(Transaction)) == txns
    assert db.scalar(select(func.count()).select_from(Alert)) == alerts
    assert r.json()["decision"] == client.post("/score", json=FRAUD, headers=auth).json()["decision"]
    assert client.post("/score/preview", json=FRAUD).status_code == 401
    assert client.post("/score/preview", json={**FRAUD, "amount": -1}, headers=auth).status_code == 422


def test_seed_cases_do_not_count_as_learned(client, auth, db):
    body = score(client, auth, FRAUD)
    assert body["decision"] == "block" and "LEARNED_FRAUD_PATTERN" not in codes(body)
    assert db.scalar(select(func.count()).select_from(FraudCase).where(FraudCase.source.in_(["feedback", "reported"]))) == 0


@pytest.mark.parametrize("neighbours, expected", [
    (Neighbours(learned_fraud=2), None),
    (Neighbours(learned_fraud=3), "review"),
    (Neighbours(learned_fraud=4), "review"),
    (Neighbours(learned_fraud=5), "block"),
    (Neighbours(learned_fraud=3, learned_legit=1), None),
    (Neighbours(learned_fraud=5, learned_legit=1), "review"),
    (Neighbours(learned_fraud=3, learned_legit=3), None),
    (Neighbours(learned_fraud=2, learned_legit=3), None),
])
def test_learned_pattern_thresholds(neighbours, expected):
    hit = learned_pattern_hit(neighbours)
    if expected is None:
        assert hit is None
    else:
        assert hit.forces_review and hit.forces_block == (expected == "block")


def test_forced_block_overrides_low_score():
    assert decide(0.0, forced_review=True) == "review"
    assert decide(0.0, forced_block=True) == "block"