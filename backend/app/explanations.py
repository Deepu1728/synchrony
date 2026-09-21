def fallback_text(decision: str, score: float, reasons: list[dict], rule_hits: list) -> str:
    head = {"block": "Blocked", "review": "Sent for review"}.get(decision, "Approved")
    parts = [f"{head} (risk score {score:.2f})."]
    if rule_hits:
        parts.append("Rules triggered: " + "; ".join(h.message for h in rule_hits) + ".")
    if reasons:
        parts.append("Model factors: " + "; ".join(r["text"] for r in reasons) + ".")
    return " ".join(parts)