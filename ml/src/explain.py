import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

ML_DIR = Path(__file__).resolve().parent.parent
DATA = ML_DIR / "data" / "features.parquet"
MODELS = ML_DIR / "models"
METRICS = ML_DIR / "metrics"
REPORTS = ML_DIR / "reports"

READABLE = {
    "amount": "transaction amount",
    "hour": "hour of day",
    "is_transfer": "transaction type (transfer vs cash-out)",
    "oldbalanceOrg": "sender balance before",
    "newbalanceOrig": "sender balance after",
    "oldbalanceDest": "receiver balance before",
    "newbalanceDest": "receiver balance after",
    "orig_zero_balance": "sender had zero balance",
    "balance_drain_ratio": "share of sender balance sent",
    "error_balance_orig": "sender balance mismatch",
    "error_balance_dest": "receiver balance mismatch",
    "sender_prior_count": "sender past transactions",
    "amount_vs_user_avg": "amount vs sender's usual amount",
    "sender_time_gap": "time since sender's last transaction",
    "sender_velocity_24h": "sender transactions in last 24h",
    "new_recipient": "first payment to this recipient",
    "dest_prior_count": "receiver past incoming transactions",
    "dest_amount_vs_avg": "amount vs receiver's usual incoming amount",
    "dest_time_gap": "time since receiver last got money",
    "dest_velocity_24h": "receiver incoming transactions in last 24h",
    "dest_first_time": "receiver never seen before",
}

_model = xgb.XGBClassifier()
_model.load_model(MODELS / "xgb.json")
_meta = json.loads((MODELS / "xgb_meta.json").read_text())
FEATURES, THRESHOLD = _meta["features"], _meta["threshold"]
_explainer = shap.TreeExplainer(_model)


def explain_transaction(row, top_k=3):
    """row: dict or Series with the model features. Returns probability, decision and top-k reasons."""
    x = pd.DataFrame([row])[FEATURES].astype(float)
    proba = float(_model.predict_proba(x)[0, 1])
    sv = _explainer.shap_values(x)[0]
    order = np.argsort(-np.abs(sv))[:top_k]
    reasons = []
    for i in order:
        name, val = FEATURES[i], float(x.iloc[0, i])
        pushes = "raises" if sv[i] > 0 else "lowers"
        reasons.append({
            "feature": name,
            "label": READABLE.get(name, name),
            "value": round(val, 4),
            "shap": round(float(sv[i]), 4),
            "direction": "increases_risk" if sv[i] > 0 else "decreases_risk",
            "text": f"{READABLE.get(name, name)} = {val:,.2f} {pushes} fraud risk",
        })
    return {"fraud_probability": round(proba, 4), "is_fraud": proba >= THRESHOLD, "reasons": reasons}


if __name__ == "__main__":
    df = pd.read_parquet(DATA).sort_values("step", kind="stable").reset_index(drop=True)
    test = df.iloc[int(len(df) * 0.8):]

    fraud = test[test.isFraud == 1].sample(1000, random_state=42)
    genuine = test[test.isFraud == 0].sample(2000, random_state=42)
    sample = pd.concat([fraud, genuine])
    X = sample[FEATURES]

    sv = _explainer.shap_values(X)

    plt.figure()
    shap.summary_plot(sv, X, show=False, max_display=12)
    plt.savefig(REPORTS / "09_shap_summary.png", dpi=150, bbox_inches="tight"); plt.close()

    plt.figure()
    shap.summary_plot(sv, X, plot_type="bar", show=False, max_display=12)
    plt.savefig(REPORTS / "10_shap_importance.png", dpi=150, bbox_inches="tight"); plt.close()

    imp = pd.Series(np.abs(sv).mean(axis=0), index=FEATURES).sort_values(ascending=False)
    (METRICS / "shap_importance.json").write_text(json.dumps(imp.round(4).to_dict(), indent=2))
    print("Top features by mean |SHAP|:")
    print(imp.head(8).round(3).to_string())

    for label, part in (("FRAUD example", fraud.iloc[0]), ("GENUINE example", genuine.iloc[0])):
        print(f"\n{label}:")
        print(json.dumps(explain_transaction(part), indent=2))