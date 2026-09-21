import json
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from app.scoring.embedding import ML_DIR

MODELS = ML_DIR / "models"
_meta = json.loads((MODELS / "xgb_meta.json").read_text())
FEATURES: list[str] = _meta["features"]
XGB_THRESHOLD: float = _meta["threshold"]

_xgb = xgb.XGBClassifier()
_xgb.load_model(MODELS / "xgb.json")

_bundle = joblib.load(MODELS / "iforest.joblib")
_iso = _bundle["model"]
_iso.n_jobs = 1
_val_scores = _bundle["val_scores"]

_explain = None


def _frame(features: dict) -> pd.DataFrame:
    return pd.DataFrame([features])[FEATURES].astype(float)


def xgb_proba(features: dict) -> float:
    return float(_xgb.predict_proba(_frame(features))[0, 1])


def anomaly_percentile(features: dict) -> float:
    raw = float(-_iso.score_samples(_frame(features))[0])
    return float(np.searchsorted(_val_scores, raw) / len(_val_scores))


def explain(features: dict, top_k: int = 3) -> list[dict]:
    global _explain
    if _explain is None:
        sys.path.insert(0, str(ML_DIR / "src"))
        import explain as explain_module

        _explain = explain_module
    return _explain.explain_transaction(features, top_k=top_k)["reasons"]


def warmup() -> None:
    sample = {name: 0.0 for name in FEATURES}
    xgb_proba(sample)
    anomaly_percentile(sample)
    explain(sample)