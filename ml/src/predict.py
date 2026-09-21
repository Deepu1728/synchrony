import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from explain import explain_transaction

ML_DIR = Path(__file__).resolve().parent.parent
_iso_bundle = joblib.load(ML_DIR / "models" / "iforest.joblib")
_iso, _val_scores = _iso_bundle["model"], _iso_bundle["val_scores"]
_features = _iso_bundle["features"]


def predict(row, top_k=3):
    """row: dict or Series with all model features. Returns decision, probability, anomaly score, reasons."""
    result = explain_transaction(row, top_k=top_k)
    x = pd.DataFrame([row])[_features].astype(float)
    raw = float(-_iso.score_samples(x)[0])
    result["anomaly_percentile"] = round(float(np.searchsorted(_val_scores, raw) / len(_val_scores)), 4)
    return result


if __name__ == "__main__":
    df = pd.read_parquet(ML_DIR / "data" / "features.parquet")
    test = df.iloc[int(len(df) * 0.8):]
    for label, part in (("fraud", test[test.isFraud == 1]), ("genuine", test[test.isFraud == 0])):
        row = part.iloc[0]
        out = predict(row)
        print(f"true label: {label}")
        print(json.dumps(out, indent=2))