import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ML_DIR = Path(__file__).resolve().parents[3] / "ml"
SCALER_PATH = ML_DIR / "models" / "embed_scaler.json"

MONEY = ["amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest",
         "newbalanceDest", "error_balance_orig", "error_balance_dest"]
COUNTS = ["dest_prior_count", "dest_amount_vs_avg", "dest_velocity_24h"]
PLAIN = ["is_transfer", "orig_zero_balance", "balance_drain_ratio",
         "dest_first_time", "dest_time_gap"]
COLUMNS = MONEY + COUNTS + PLAIN + ["hour_sin", "hour_cos"]
DIM = len(COLUMNS)


def _transform(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c in MONEY:
        out[c] = np.sign(df[c]) * np.log1p(np.abs(df[c]))
    for c in COUNTS:
        out[c] = np.log1p(df[c].clip(lower=0))
    for c in PLAIN:
        out[c] = df[c].astype(float)
    angle = 2 * np.pi * df["hour"] / 24
    out["hour_sin"] = np.sin(angle)
    out["hour_cos"] = np.cos(angle)
    return out[COLUMNS]


def fit_scaler(train_df: pd.DataFrame) -> None:
    t = _transform(train_df)
    scaler = {
        "columns": COLUMNS,
        "mean": t.mean().tolist(),
        "std": t.std().clip(lower=1e-6).tolist(),
    }
    SCALER_PATH.write_text(json.dumps(scaler, indent=2))
    load_scaler.cache_clear()


@lru_cache
def load_scaler():
    s = json.loads(SCALER_PATH.read_text())
    return np.array(s["mean"]), np.array(s["std"])


def embed_frame(df: pd.DataFrame) -> np.ndarray:
    mean, std = load_scaler()
    return ((_transform(df).to_numpy() - mean) / std).astype(np.float32)


def embed_one(features: dict) -> list[float]:
    return embed_frame(pd.DataFrame([features]))[0].tolist()