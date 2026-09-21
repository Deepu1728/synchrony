import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (ConfusionMatrixDisplay, average_precision_score,
                             confusion_matrix, f1_score, precision_recall_curve,
                             precision_score, recall_score)

DATA = "../data/features.parquet"
MODELS = Path("../models")
METRICS = Path("../metrics")
REPORTS = Path("../reports")
for p in (MODELS, METRICS, REPORTS):
    p.mkdir(exist_ok=True)

df = pd.read_parquet(DATA).sort_values("step", kind="stable").reset_index(drop=True)
features = [c for c in df.columns if c not in ("isFraud", "step")]

n = len(df)
train_end, val_end = int(n * 0.6), int(n * 0.8)
train, val, test = df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]
for name, part in (("train", train), ("val", val), ("test", test)):
    print(f"{name}: rows={len(part):,} steps {part.step.min()}-{part.step.max()} fraud={int(part.isFraud.sum())}")

X_tr, y_tr = train[features], train.isFraud
X_va, y_va = val[features], val.isFraud
X_te, y_te = test[features], test.isFraud

spw = (y_tr == 0).sum() / (y_tr == 1).sum()
print(f"scale_pos_weight = {spw:.1f}")

model = xgb.XGBClassifier(
    n_estimators=600,
    learning_rate=0.05,
    max_depth=6,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=spw,
    eval_metric="aucpr",
    early_stopping_rounds=30,
    tree_method="hist",
    n_jobs=-1,
    random_state=42,
)
model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=50)

val_proba = model.predict_proba(X_va)[:, 1]
prec, rec, thr = precision_recall_curve(y_va, val_proba)
f1 = 2 * prec[:-1] * rec[:-1] / np.clip(prec[:-1] + rec[:-1], 1e-9, None)
threshold = float(thr[np.argmax(f1)])
print(f"threshold (max F1 on validation) = {threshold:.4f}")

test_proba = model.predict_proba(X_te)[:, 1]
pred = (test_proba >= threshold).astype(int)
cm = confusion_matrix(y_te, pred)
tn, fp, fn, tp = cm.ravel()
metrics = {
    "split": {"train_rows": len(train), "val_rows": len(val), "test_rows": len(test),
              "test_fraud": int(y_te.sum())},
    "threshold": threshold,
    "precision": float(precision_score(y_te, pred)),
    "recall": float(recall_score(y_te, pred)),
    "f1": float(f1_score(y_te, pred)),
    "pr_auc": float(average_precision_score(y_te, test_proba)),
    "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    "baseline_pr_auc": float(y_te.mean()),
    "best_iteration": int(model.best_iteration),
}
print(json.dumps(metrics, indent=2))

p_te, r_te, _ = precision_recall_curve(y_te, test_proba)
plt.figure(figsize=(6, 5))
plt.plot(r_te, p_te, color="#c44e52", label=f"XGBoost (PR-AUC {metrics['pr_auc']:.3f})")
plt.axhline(metrics["baseline_pr_auc"], color="grey", ls="--", label="Random baseline")
plt.scatter([metrics["recall"]], [metrics["precision"]], color="black", zorder=5, label="Chosen threshold")
plt.xlabel("Recall"); plt.ylabel("Precision"); plt.title("Precision-Recall curve (test)")
plt.legend(); plt.savefig(REPORTS / "06_xgb_pr_curve.png", dpi=150, bbox_inches="tight"); plt.close()

ConfusionMatrixDisplay(cm, display_labels=["Genuine", "Fraud"]).plot(cmap="Blues", values_format="d")
plt.title("Confusion matrix (test)")
plt.savefig(REPORTS / "07_xgb_confusion_matrix.png", dpi=150, bbox_inches="tight"); plt.close()

model.save_model(MODELS / "xgb.json")
(MODELS / "xgb_meta.json").write_text(json.dumps({"features": features, "threshold": threshold}, indent=2))
(METRICS / "xgb_metrics.json").write_text(json.dumps(metrics, indent=2))
print("saved model, metrics, plots")