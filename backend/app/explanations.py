import logging

from sqlalchemy.orm import joinedload

from app import llm
from app.db import SessionLocal
from app.models import Alert

logger = logging.getLogger(__name__)


def fallback_text(decision: str, score: float, reasons: list[dict], rule_hits: list) -> str:
    head = {"block": "Blocked", "review": "Sent for review"}.get(decision, "Approved")
    parts = [f"{head} (risk score {score:.2f})."]
    if rule_hits:
        parts.append("Rules triggered: " + "; ".join(h.message for h in rule_hits) + ".")
    if reasons:
        parts.append("Model factors: " + "; ".join(r["text"] for r in reasons) + ".")
    return " ".join(parts)


def improve_explanation(db, alert, client=None) -> str:
    text = llm.generate(llm.build_facts(alert), client=client)
    if text is None:
        return alert.explanation_source
    alert.explanation_text = text
    alert.explanation_source = "llm"
    db.commit()
    return "llm"


def explain_in_background(alert_id: int, session_factory=SessionLocal) -> None:
    if not llm.is_enabled():
        return
    try:
        with session_factory() as db:
            alert = db.get(Alert, alert_id, options=[joinedload(Alert.transaction)])
            if alert and alert.explanation_source == "shap_fallback":
                improve_explanation(db, alert)
    except Exception:
        logger.exception("background explanation failed")