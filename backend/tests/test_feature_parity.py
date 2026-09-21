import sys

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app import models
from app.db import engine
from app.schemas import TransactionIn
from app.scoring import embedding
from app.scoring.features import build_features

sys.path.insert(0, str(embedding.ML_DIR / "src"))
import features as offline  # noqa: E402


def synthetic_paysim(n=1500, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    senders = [f"C{1000000 + i}" for i in range(50)]
    receivers = [f"C{2000000 + i}" for i in range(35)]
    steps = np.sort(rng.integers(1, 120, n))
    orig = rng.choice(senders, n)
    dest = rng.choice(receivers, n)
    amount = np.round(rng.lognormal(9, 1.5, n), 2)
    old_o = np.round(amount * rng.choice([0, 0.5, 1, 1, 3], n), 2)
    old_d = np.round(rng.lognormal(8, 2, n) * rng.integers(0, 2, n), 2)
    return pd.DataFrame({
        "step": steps,
        "type": rng.choice(["TRANSFER", "CASH_OUT"], n),
        "amount": amount,
        "nameOrig": orig,
        "oldbalanceOrg": old_o,
        "newbalanceOrig": np.maximum(old_o - amount, 0),
        "nameDest": dest,
        "oldbalanceDest": old_d,
        "newbalanceDest": old_d + amount,
        "isFraud": rng.integers(0, 2, n),
        "isFlaggedFraud": 0,
    })


def test_online_features_match_offline(tmp_path):
    raw = synthetic_paysim()
    csv = tmp_path / "paysim.csv"
    raw.to_csv(csv, index=False)
    expected = offline.build(str(csv)).drop(columns=["step", "isFraud"])
    ordered = raw.sort_values("step", kind="stable").reset_index(drop=True)

    db = Session(engine)
    try:
        online_rows = []
        for r in ordered.itertuples():
            txn = TransactionIn(
                step=int(r.step), type=r.type, amount=float(r.amount),
                name_orig=r.nameOrig, oldbalance_org=float(r.oldbalanceOrg),
                newbalance_orig=float(r.newbalanceOrig), name_dest=r.nameDest,
                oldbalance_dest=float(r.oldbalanceDest), newbalance_dest=float(r.newbalanceDest),
            )
            feats = build_features(db, txn)
            online_rows.append(feats)
            db.add(models.Transaction(
                step=txn.step, type=txn.type, amount=txn.amount, name_orig=txn.name_orig,
                oldbalance_org=txn.oldbalance_org, newbalance_orig=txn.newbalance_orig,
                name_dest=txn.name_dest, oldbalance_dest=txn.oldbalance_dest,
                newbalance_dest=txn.newbalance_dest, features=feats, xgb_proba=0.0,
                anomaly_percentile=0.0, similarity_score=0.0, combined_score=0.0, decision="approve",
            ))
            db.flush()
    finally:
        db.rollback()
        db.close()

    online = pd.DataFrame(online_rows)[list(expected.columns)]
    assert (expected.dest_prior_count > 0).mean() > 0.5
    pd.testing.assert_frame_equal(online.astype(float), expected.astype(float), rtol=1e-9, atol=1e-9)