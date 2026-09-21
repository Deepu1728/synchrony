from sqlalchemy import func, select

from app.models import Alert, Feedback, FraudCase, Transaction

FRAUD = {
    "step": 4, "type": "TRANSFER", "amount": 692654.27,
    "name_orig": "C1231006815", "oldbalance_org": 692654.27, "newbalance_orig": 0,
    "name_dest": "C553264065", "oldbalance_dest": 0, "newbalance_dest": 0,
}
GENUINE = {
    "step": 14, "type": "CASH_OUT", "amount": 8500,
    "name_orig": "C840083671", "oldbalance_org": 20632, "newbalance_orig": 12132,
    "name_dest": "C38997010", "oldbalance_dest": 21182, "newbalance_dest": 29682,
}


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_fraud_is_blocked_and_creates_alert(client, auth, db):
    r = client.post("/score", json=FRAUD, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "block" and body["alert_id"]
    assert len(body["reasons"]) == 6 and body["explanation"].startswith("Blocked")
    assert {x["code"] for x in body["rules"]} >= {"FULL_BALANCE_DRAIN"}
    assert body["latency_ms"] > 0
    txn = db.get(Transaction, body["transaction_id"])
    assert txn.decision == "block" and txn.features["dest_first_time"] == 1


def test_genuine_is_approved_without_alert(client, auth, db):
    before = count(db, Alert)
    r = client.post("/score", json=GENUINE, headers=auth)
    body = r.json()
    assert body["decision"] == "approve" and body["alert_id"] is None and body["reasons"] == []
    assert count(db, Alert) == before
    assert db.get(Transaction, body["transaction_id"]) is not None


def test_history_accumulates_across_requests(client, auth, db):
    first = client.post("/score", json=GENUINE, headers=auth).json()
    second = client.post("/score", json={**GENUINE, "step": 15}, headers=auth).json()
    f1 = db.get(Transaction, first["transaction_id"]).features
    f2 = db.get(Transaction, second["transaction_id"]).features
    assert f1["dest_prior_count"] == 0 and f2["dest_prior_count"] == 1
    assert f2["new_recipient"] == 0 and f2["sender_prior_count"] == 1


def test_alert_list_filters_and_pagination(client, auth):
    before = client.get("/alerts", headers=auth).json()["total"]
    a = client.post("/score", json=FRAUD, headers=auth).json()["alert_id"]
    b = client.post("/score", json={**FRAUD, "name_orig": "C1231006816"}, headers=auth).json()["alert_id"]
    listing = client.get("/alerts?limit=1", headers=auth).json()
    assert listing["total"] == before + 2 and len(listing["items"]) == 1
    assert listing["items"][0]["id"] == max(a, b)
    item = listing["items"][0]
    assert item["status"] == "open" and item["transaction"]["amount"] == 692654.27
    assert client.get("/alerts?status=confirmed_fraud&limit=200", headers=auth).json()["total"] >= 0
    assert client.get(f"/alerts/{a}", headers=auth).json()["id"] == a
    assert client.get("/alerts/99999999", headers=auth).status_code == 404
    assert client.get("/alerts?limit=0", headers=auth).status_code == 422
    assert client.get("/alerts?status=bogus", headers=auth).status_code == 422


def test_feedback_fraud_updates_alert_and_grows_case_store(client, auth, db):
    alert_id = client.post("/score", json=FRAUD, headers=auth).json()["alert_id"]
    cases = count(db, FraudCase)
    r = client.post("/feedback", json={"alert_id": alert_id, "verdict": "fraud", "note": "confirmed by call"}, headers=auth)
    assert r.status_code == 201
    assert r.json()["alert_status"] == "confirmed_fraud" and r.json()["case_added"] is True
    assert count(db, FraudCase) == cases + 1
    case = db.scalars(select(FraudCase).order_by(FraudCase.id.desc()).limit(1)).one()
    assert case.label == "fraud" and case.source == "feedback"
    assert count(db, Feedback) >= 1
    again = client.post("/feedback", json={"alert_id": alert_id, "verdict": "legit"}, headers=auth)
    assert again.status_code == 409


def test_feedback_legit_marks_false_positive(client, auth, db):
    alert_id = client.post("/score", json=FRAUD, headers=auth).json()["alert_id"]
    r = client.post("/feedback", json={"alert_id": alert_id, "verdict": "legit"}, headers=auth)
    assert r.json()["alert_status"] == "false_positive"
    assert db.scalars(select(FraudCase).order_by(FraudCase.id.desc()).limit(1)).one().label == "legit"


def test_feedback_validation_and_missing_alert(client, auth):
    assert client.post("/feedback", json={"alert_id": 99999999, "verdict": "fraud"}, headers=auth).status_code == 404
    assert client.post("/feedback", json={"alert_id": 1, "verdict": "maybe"}, headers=auth).status_code == 422
    assert client.post("/feedback", json={"alert_id": 0, "verdict": "fraud"}, headers=auth).status_code == 422
    assert client.post("/feedback", json={"alert_id": 1, "verdict": "fraud", "note": "x" * 501}, headers=auth).status_code == 422


def test_endpoints_require_token(client):
    assert client.get("/alerts").status_code == 401
    assert client.get("/alerts/1").status_code == 401
    assert client.post("/feedback", json={"alert_id": 1, "verdict": "fraud"}).status_code == 401
    assert client.post("/score", json=FRAUD).status_code == 401