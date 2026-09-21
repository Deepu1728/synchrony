import json
from pathlib import Path

import pandas as pd

ML_DIR = Path(__file__).resolve().parent.parent
RAW = ML_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
FEATURES = ML_DIR / "data" / "features.parquet"
METRICS = ML_DIR / "metrics"

raw = pd.read_csv(RAW, usecols=["type", "isFraud"])
modeled = pd.read_parquet(FEATURES, columns=["isFraud"])

xgb_m = json.loads((METRICS / "xgb_metrics.json").read_text())
cmp_m = json.loads((METRICS / "model_comparison.json").read_text())
shap_m = json.loads((METRICS / "shap_importance.json").read_text())
meta = json.loads((ML_DIR / "models" / "xgb_meta.json").read_text())

summary = {
    "dataset": {
        "name": "PaySim (synthetic mobile money)",
        "rows_total": int(len(raw)),
        "fraud_total": int(raw.isFraud.sum()),
        "fraud_rate_total": float(raw.isFraud.mean()),
        "imbalance_ratio": round((len(raw) - raw.isFraud.sum()) / raw.isFraud.sum(), 1),
        "rows_modeled": int(len(modeled)),
        "modeled_types": ["TRANSFER", "CASH_OUT"],
        "fraud_rate_modeled": float(modeled.isFraud.mean()),
    },
    "split": {"method": "time-based on step: 60% train / 20% validation / 20% test", **xgb_m["split"]},
    "xgboost": {
        "threshold": xgb_m["threshold"],
        "precision": xgb_m["precision"],
        "recall": xgb_m["recall"],
        "f1": xgb_m["f1"],
        "pr_auc": xgb_m["pr_auc"],
        "baseline_pr_auc": xgb_m["baseline_pr_auc"],
        "confusion_matrix": xgb_m["confusion_matrix"],
        "n_features": len(meta["features"]),
    },
    "isolation_forest": next(r for r in cmp_m["comparison"] if r["model"].startswith("Isolation")),
    "top_shap_features": dict(list(shap_m.items())[:8]),
    "caveats": [
        "PaySim is synthetic; near-perfect scores reflect clean simulator patterns, not real-world fraud.",
        "Senders almost never repeat in PaySim, so sender-history features carry little signal.",
        "Isolation Forest is weak here; XGBoost makes the decision, IForest is a secondary anomaly score.",
    ],
}
(METRICS / "metrics.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))