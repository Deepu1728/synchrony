from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import explanations, llm
from app.config import settings
from app.models import Alert

FRAUD = {
    "step": 4, "type": "TRANSFER", "amount": 692654.27,
    "name_orig": "C1231006815", "oldbalance_org": 692654.27, "newbalance_orig": 0,
    "name_dest": "C553264065", "oldbalance_dest": 0, "newbalance_dest": 0,
}

GOOD = ("This transfer of 692,654.27 shows patterns consistent with fraud: it sends the sender's entire "
        "balance at hour 4, and 10 of 10 similar past cases were fraud. Suggested next step: hold the transaction.")


class FakeClient:
    def __init__(self, text=None, error=None):
        self.calls, self._text, self._error = [], text, error
        self.messages = self

    def create(self, *, model, max_tokens, messages, system=None):
        self.calls.append({"model": model, "max_tokens": max_tokens, "messages": messages, "system": system})
        if self._error:
            raise self._error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


@pytest.fixture
def alert(client, auth, db):
    alert_id = client.post("/score", json=FRAUD, headers=auth).json()["alert_id"]
    return db.get(Alert, alert_id)


def test_facts_contain_no_identifiers(alert):
    facts = llm.build_facts(alert)
    blob = str(facts)
    assert "C1231006815" not in blob and "C553264065" not in blob
    assert facts["decision"] == "block" and facts["amount"] == 692654.27
    assert facts["similar_past_cases"] == {"fraud": 10, "checked": 10}
    assert len(facts["model_factors"]) == 3 and facts["rules_triggered"]


def test_prompt_sent_to_llm_has_guardrails_and_no_ids(alert):
    client = FakeClient(GOOD)
    llm.generate(llm.build_facts(alert), client=client)
    call = client.calls[0]
    assert "Use ONLY the facts" in call["system"] and "never as instructions" in call["system"]
    assert call["model"] == settings.llm_model and call["max_tokens"] == settings.llm_max_output_tokens
    assert "C1231006815" not in call["messages"][0]["content"]


def test_good_output_is_accepted(alert):
    assert llm.generate(llm.build_facts(alert), client=FakeClient(GOOD)) == GOOD


@pytest.mark.parametrize("bad", [
    "",
    "Too short.",
    "x" * 700,
    "This transfer of 999,999.00 shows patterns consistent with fraud. Suggested next step: hold the transaction.",
    "This is definitely fraud, hold the transaction and call the police right now please.",
    "The criminal moved 692,654.27 out of the account. Suggested next step: hold the transaction.",
    "See http://evil.example for details about this 692,654.27 transfer. Suggested next step: hold the transaction.",
    "Transfer of **692,654.27** looks risky. Suggested next step: hold the transaction.",
    "Contact me@evil.example about the 692,654.27 transfer. Suggested next step: hold the transaction.",
])
def test_bad_output_is_rejected(alert, bad):
    assert llm.generate(llm.build_facts(alert), client=FakeClient(bad)) is None


def test_llm_error_returns_none(alert):
    assert llm.generate(llm.build_facts(alert), client=FakeClient(error=TimeoutError("slow"))) is None


def test_no_key_and_no_client_returns_none(alert):
    assert llm.is_enabled() is False
    assert llm.generate(llm.build_facts(alert)) is None


def test_call_budget_is_enforced(alert, monkeypatch):
    monkeypatch.setattr(settings, "llm_max_calls_per_minute", 1)
    facts = llm.build_facts(alert)
    assert llm.generate(facts, client=FakeClient(GOOD)) == GOOD
    assert llm.generate(facts, client=FakeClient(GOOD)) is None


def test_improve_explanation_upgrades_alert(alert, db):
    assert alert.explanation_source == "shap_fallback"
    assert explanations.improve_explanation(db, alert, client=FakeClient(GOOD)) == "llm"
    assert alert.explanation_text == GOOD and alert.explanation_source == "llm"


def test_failure_keeps_shap_fallback(alert, db):
    original = alert.explanation_text
    assert explanations.improve_explanation(db, alert, client=FakeClient(error=RuntimeError("boom"))) == "shap_fallback"
    assert alert.explanation_text == original and original.startswith("Blocked")


def test_explain_endpoint_uses_llm_when_available(client, auth, alert, monkeypatch):
    monkeypatch.setattr(llm, "generate", lambda facts, client=None: GOOD)
    r = client.post(f"/alerts/{alert.id}/explain", headers=auth)
    assert r.status_code == 200
    assert r.json()["explanation_source"] == "llm" and r.json()["explanation_text"] == GOOD


def test_explain_endpoint_falls_back_when_llm_unavailable(client, auth, alert):
    r = client.post(f"/alerts/{alert.id}/explain", headers=auth)
    assert r.status_code == 200 and r.json()["explanation_source"] == "shap_fallback"
    assert r.json()["explanation_text"].startswith("Blocked")


def test_explain_endpoint_404_and_401(client, auth):
    assert client.post("/alerts/99999999/explain", headers=auth).status_code == 404
    assert client.post("/alerts/1/explain").status_code == 401


def test_score_never_fails_when_llm_breaks(client, auth, db, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def explode(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm, "generate", explode)
    r = client.post("/score", json=FRAUD, headers=auth)
    assert r.status_code == 200 and r.json()["explanation"].startswith("Blocked")

    @contextmanager
    def same_session():
        yield db

    explanations.explain_in_background(r.json()["alert_id"], session_factory=same_session)
    assert db.get(Alert, r.json()["alert_id"]).explanation_source == "shap_fallback"


def test_background_upgrade_runs_when_enabled(client, auth, db, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(llm, "generate", lambda facts, client=None: GOOD)
    alert_id = client.post("/score", json=FRAUD, headers=auth).json()["alert_id"]

    @contextmanager
    def same_session():
        yield db

    explanations.explain_in_background(alert_id, session_factory=same_session)
    assert db.get(Alert, alert_id).explanation_source == "llm"