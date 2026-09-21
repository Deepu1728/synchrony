import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (average_precision_score, f1_score,
                             precision_recall_curve, precision_score,
                             recall_score)

DATA = "../data/features.parquet"
MODELS = Path("../models")
METRICS = Path("../metrics")
REPORTS = Path("../reports")

df = pd.read_parquet(DATA).sort_values("step", kind="stable").reset_index(drop=True)
features = json.loads((MODELS / "xgb_meta.json").read_text())["features"]

n = len(df)
train_end, val_end = int(n * 0.6), int(n * 0.8)
train, val, test = df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]

genuine_train = train[train.isFraud == 0]
print(f"fitting on {len(genuine_train):,} genuine train rows")

iso = IsolationForest(n_estimators=200, max_samples=1024, random_state=42, n_jobs=-1)
iso.fit(genuine_train[features])

s_val = -iso.score_samples(val[features])
s_te = -iso.score_samples(test[features])
y_val, y_te = val.isFraud.to_numpy(), test.isFraud.to_numpy()

xgb_model = xgb.XGBClassifier()
xgb_model.load_model(MODELS / "xgb.json")
x_val = xgb_model.predict_proba(val[features])[:, 1]
x_te = xgb_model.predict_proba(test[features])[:, 1]


def best_f1_threshold(y, s):
    p, r, t = precision_recall_curve(y, s)
    f1 = 2 * p[:-1] * r[:-1] / np.clip(p[:-1] + r[:-1], 1e-9, None)
    return float(t[np.argmax(f1)])


def recall_at_precision(y, s, target):
    p, r, _ = precision_recall_curve(y, s)
    ok = p >= target
    return float(r[ok].max()) if ok.any() else 0.0


def evaluate(name, s_val_, s_te_):
    thr = best_f1_threshold(y_val, s_val_)
    pred = (s_te_ >= thr).astype(int)
    return {
        "model": name,
        "pr_auc": float(average_precision_score(y_te, s_te_)),
        "precision": float(precision_score(y_te, pred, zero_division=0)),
        "recall": float(recall_score(y_te, pred)),
        "f1": float(f1_score(y_te, pred)),
        "recall_at_precision_90": recall_at_precision(y_te, s_te_, 0.90),
        "recall_at_precision_50": recall_at_precision(y_te, s_te_, 0.50),
    }


rows = [evaluate("XGBoost (supervised)", x_val, x_te),
        evaluate("IsolationForest (unsupervised)", s_val, s_te)]
table = pd.DataFrame(rows).set_index("model")
print(table.round(4).T.to_string())

out = {
    "iforest_threshold_f1": best_f1_threshold(y_val, s_val),
    "genuine_median_score": float(np.median(s_val[y_val == 0])),
    "fraud_median_score": float(np.median(s_val[y_val == 1])),
    "comparison": rows,
}
(METRICS / "model_comparison.json").write_text(json.dumps(out, indent=2))
table.round(4).to_csv(REPORTS / "08_model_comparison.csv")
joblib.dump({"model": iso, "features": features, "val_scores": np.sort(s_val)}, MODELS / "iforest.joblib")

plt.figure(figsize=(6, 5))
for name, st in (("XGBoost", x_te), ("IsolationForest", s_te)):
    p, r, _ = precision_recall_curve(y_te, st)
    plt.plot(r, p, label=f"{name} (AP {average_precision_score(y_te, st):.3f})")
plt.axhline(y_te.mean(), color="grey", ls="--", label="Random")
plt.xlabel("Recall"); plt.ylabel("Precision"); plt.title("PR curves on test: model comparison")
plt.legend(); plt.savefig(REPORTS / "08_model_comparison.png", dpi=150, bbox_inches="tight"); plt.close()
print("saved iforest.joblib, comparison json/csv/png")
