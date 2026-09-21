import pytest

from app.config import settings
from app.routers.metrics import ratio

BENIGN = {
    "step": 14, "type": "CASH_OUT", "amount": 8500, "oldbalance_org": 20632, "newbalance_orig": 12132,
    "oldbalance_dest": 21182, "newbalance_dest": 29682,
}
FRAUD = {
    "step": 4, "type": "TRANSFER", "amount": 692654.27, "oldbalance_org": 692654.27,
    "newbalance_orig": 0, "oldbalance_dest": 0, "newbalance_dest": 0,
}


def benign(i: int, label=None) -> dict:
    payload = {**BENIGN, "name_orig": f"C{5000000 + i}", "name_dest": f"C{6000000 + i}"}
    return payload if label is None else {**payload, "true_label": label}


def fraud(i: int, label=None) -> dict:
    payload = {**FRAUD, "name_orig": f"C{7000000 + i}", "name_dest": f"C{8000000 + i}"}
    return payload if label is None else {**payload, "true_label": label}


def score(client, auth, payload) -> dict:
    r = client.post("/score", json=payload, headers=auth)
    assert r.status_code == 200
    return r.json()


def get(client, auth, url):
    return client.get(url, headers=auth)


def test_feed_cursor_returns_only_new_rows_in_order(client, auth):
    cursor = get(client, auth, "/transactions?limit=1").json()["last_id"] or 0
    a, b, c = score(client, auth, benign(1)), score(client, auth, fraud(1)), score(client, auth, benign(2))
    ids = [a["transaction_id"], b["transaction_id"], c["transaction_id"]]

    feed = get(client, auth, f"/transactions?after_id={cursor}").json()
    assert [row["id"] for row in feed["items"]] == ids and feed["last_id"] == ids[-1]
    approve1, block, approve2 = feed["items"]
    assert (approve1["decision"], block["decision"], approve2["decision"]) == ("approve", "block", "approve")
    assert approve1["alert_id"] is None and block["alert_id"] == b["alert_id"] and block["alert_status"] == "open"
    assert block["type"] == "TRANSFER" and block["amount"] == 692654.27 and block["score"] == pytest.approx(b["combined_score"])
    assert {"id", "created_at", "step", "name_orig", "name_dest", "true_label"} <= set(block)

    assert get(client, auth, f"/transactions?after_id={ids[-1]}").json() == {"items": [], "last_id": ids[-1]}
    two = get(client, auth, f"/transactions?after_id={cursor}&limit=2").json()
    assert [r["id"] for r in two["items"]] == ids[:2] and two["last_id"] == ids[1]
    blocks = get(client, auth, f"/transactions?after_id={cursor}&decision=block").json()
    assert [r["id"] for r in blocks["items"]] == [ids[1]]
    latest = get(client, auth, "/transactions?limit=3").json()
    assert [r["id"] for r in latest["items"]] == ids


def test_feed_validation_and_auth(client, auth):
    for bad in ("limit=0", "limit=501", "after_id=-1", "decision=bogus"):
        assert get(client, auth, f"/transactions?{bad}").status_code == 422
    assert client.get("/transactions").status_code == 401


def test_alert_detail_has_scores_thresholds_and_six_factors(client, auth):
    body = score(client, auth, fraud(10))
    alert = get(client, auth, f"/alerts/{body['alert_id']}").json()
    assert set(alert["scores"]) == {"model", "similarity", "anomaly", "rules", "combined"}
    assert alert["scores"]["combined"] == pytest.approx(body["combined_score"])
    assert alert["scores"]["model"] == pytest.approx(body["xgb_proba"])
    assert alert["thresholds"] == {"review": settings.review_threshold, "block": settings.block_threshold}
    assert len(alert["reasons"]) == 6
    magnitudes = [abs(r["shap"]) for r in alert["reasons"]]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert alert["explanation_text"].count("fraud risk") == 3
    tx = alert["transaction"]
    assert tx["oldbalance_org"] == 692654.27 and tx["newbalance_orig"] == 0 and "created_at" in tx
    assert alert["feedback"] is None


def test_alert_detail_shows_who_reviewed_it_but_the_list_does_not(client, auth):
    alert_id = score(client, auth, fraud(11))["alert_id"]
    r = client.post("/feedback", json={"alert_id": alert_id, "verdict": "fraud", "note": "confirmed by call"}, headers=auth)
    assert r.status_code == 201
    detail = get(client, auth, f"/alerts/{alert_id}").json()
    assert detail["status"] == "confirmed_fraud"
    assert {k: detail["feedback"][k] for k in ("verdict", "username", "note")} == {
        "verdict": "fraud", "username": "admin", "note": "confirmed by call"}
    listed = get(client, auth, "/alerts?limit=200").json()["items"]
    assert next(a for a in listed if a["id"] == alert_id)["feedback"] is None


def test_similar_cases_match_scoring_and_are_sorted(client, auth):
    body = score(client, auth, fraud(20))
    sim = get(client, auth, f"/alerts/{body['alert_id']}/similar").json()
    assert sim["alert_id"] == body["alert_id"] and sim["k"] == 10 and len(sim["cases"]) == 10
    distances = [c["distance"] for c in sim["cases"]]
    assert distances == sorted(distances) and all(d >= 0 for d in distances)
    assert sim["summary"]["fraud"] == body["fraud_neighbours"]
    assert sim["summary"]["fraud"] + sim["summary"]["legit"] == 10
    assert all(c["label"] in ("fraud", "legit") and c["source"] == "paysim_train" for c in sim["cases"])
    assert all(c["type"] in ("TRANSFER", "CASH_OUT") and c["amount"] > 0 and 0 <= c["hour"] <= 23 for c in sim["cases"])
    assert len(get(client, auth, f"/alerts/{body['alert_id']}/similar?k=3").json()["cases"]) == 3


def test_similar_cases_link_analyst_labelled_alerts_and_skip_the_alerts_own_case(client, auth):
    first, second = score(client, auth, fraud(30)), score(client, auth, fraud(31))
    assert client.post("/feedback", json={"alert_id": first["alert_id"], "verdict": "fraud"}, headers=auth).status_code == 201
    sim = get(client, auth, f"/alerts/{second['alert_id']}/similar").json()
    linked = [c for c in sim["cases"] if c["alert_id"] == first["alert_id"]]
    assert linked and linked[0]["source"] == "feedback" and linked[0]["label"] == "fraud"
    assert sim["summary"]["learned_fraud"] >= 1

    assert client.post("/feedback", json={"alert_id": second["alert_id"], "verdict": "fraud"}, headers=auth).status_code == 201
    again = get(client, auth, f"/alerts/{second['alert_id']}/similar").json()
    assert all(c["alert_id"] != second["alert_id"] for c in again["cases"])


def test_similar_cases_validation_and_auth(client, auth):
    alert_id = score(client, auth, fraud(40))["alert_id"]
    assert get(client, auth, f"/alerts/{alert_id}/similar?k=0").status_code == 422
    assert get(client, auth, f"/alerts/{alert_id}/similar?k=51").status_code == 422
    assert get(client, auth, "/alerts/99999999/similar").status_code == 404
    assert client.get(f"/alerts/{alert_id}/similar").status_code == 401


def test_metrics_for_a_known_mix(client, auth):
    fraud_blocked = [score(client, auth, fraud(i, True)) for i in (50, 51)]
    score(client, auth, benign(50, True))
    for i in (51, 52, 53):
        score(client, auth, benign(i, False))
    false_alarm = score(client, auth, fraud(52, False))
    score(client, auth, benign(54))

    m = get(client, auth, "/metrics?window_minutes=1").json()
    assert m["window_minutes"] == 1
    assert m["decisions"] == {"total": 8, "approve": 5, "review": 0, "block": 3}
    gt = m["ground_truth"]
    assert (gt["labelled"], gt["fraud_total"], gt["fraud_flagged"], gt["fraud_blocked"]) == (7, 3, 2, 2)
    assert (gt["genuine_total"], gt["genuine_flagged"], gt["genuine_blocked"]) == (4, 1, 1)
    assert gt["catch_rate"] == pytest.approx(0.6667, abs=1e-4) and gt["block_catch_rate"] == pytest.approx(0.6667, abs=1e-4)
    assert gt["false_positive_rate"] == 0.25 and gt["false_block_rate"] == 0.25
    assert gt["precision_flagged"] == pytest.approx(0.6667, abs=1e-4) and gt["precision_block"] == pytest.approx(0.6667, abs=1e-4)
    assert gt["stream_fraud_share"] == pytest.approx(0.4286, abs=1e-4)
    assert m["alerts"] == {"open": 3, "confirmed_fraud": 0, "false_positive": 0, "reviewed": 0, "analyst_precision": None}
    assert "simulator" in m["note"]

    for body, verdict in ((fraud_blocked[0], "fraud"), (false_alarm, "legit")):
        assert client.post("/feedback", json={"alert_id": body["alert_id"], "verdict": verdict}, headers=auth).status_code == 201
    after = get(client, auth, "/metrics?window_minutes=1").json()
    assert after["alerts"] == {"open": 1, "confirmed_fraud": 1, "false_positive": 1, "reviewed": 2, "analyst_precision": 0.5}
    assert after["learned_cases"] == {"fraud": 1, "legit": 1}
    everything = get(client, auth, "/metrics").json()
    assert everything["window_minutes"] is None and everything["decisions"]["total"] >= 8


def test_metrics_rates_are_none_without_ground_truth(client, auth):
    score(client, auth, benign(60))
    gt = get(client, auth, "/metrics?window_minutes=1").json()["ground_truth"]
    assert gt["labelled"] == 0 and gt["catch_rate"] is None and gt["false_positive_rate"] is None
    assert gt["precision_flagged"] is None and gt["stream_fraud_share"] is None


def test_metrics_validation_and_auth(client, auth):
    for bad in ("window_minutes=0", "window_minutes=-5", "window_minutes=abc"):
        assert get(client, auth, f"/metrics?{bad}").status_code == 422
    assert client.get("/metrics").status_code == 401


def test_ratio_helper():
    assert ratio(1, 3) == 0.3333 and ratio(5, 5) == 1.0
    assert ratio(0, 4) == 0.0 and ratio(3, 0) is None