import numpy as np
import pandas as pd

RAW = "../data/PS_20174392719_1491204439457_log.csv"
OUT = "../data/features.parquet"
WINDOW = 24


def history(keys, steps, amounts, window=WINDOW):
    gid = pd.factorize(keys)[0].astype(np.int64)
    n = len(gid)
    order = np.lexsort((np.arange(n), steps, gid))
    g, s, a = gid[order], steps[order], amounts[order]

    first = np.r_[True, g[1:] != g[:-1]]
    start = np.maximum.accumulate(np.where(first, np.arange(n), 0))
    prior_count = np.arange(n) - start

    excl = np.cumsum(a) - a
    prior_sum = excl - excl[start]
    prior_avg = np.where(prior_count > 0, prior_sum / np.maximum(prior_count, 1), np.nan)

    prev_step = np.r_[np.nan, s[:-1]]
    time_gap = np.where(prior_count > 0, s - prev_step, np.nan)

    comp = g * 100000 + s
    lower = np.searchsorted(comp, g * 100000 + (s - window), side="left")
    velocity = np.arange(n) - np.maximum(lower, start)

    inv = np.empty(n, dtype=np.int64)
    inv[order] = np.arange(n)
    return prior_count[inv], prior_avg[inv], time_gap[inv], velocity[inv]


def ratio_to_avg(amount, avg):
    r = amount / avg.where(avg > 0)
    return r.fillna(1.0).clip(upper=1000)


def build(raw_path=RAW):
    df = pd.read_csv(raw_path)
    df = df[df.type.isin(["TRANSFER", "CASH_OUT"])].drop(columns="isFlaggedFraud")
    df = df.sort_values("step", kind="stable").reset_index(drop=True)

    steps = df.step.to_numpy(dtype=np.int64)
    amt = df.amount.to_numpy(dtype=np.float64)

    f = pd.DataFrame(index=df.index)
    f["step"] = df.step
    f["hour"] = df.step % 24
    f["is_transfer"] = (df.type == "TRANSFER").astype(int)
    f["amount"] = df.amount
    f["oldbalanceOrg"] = df.oldbalanceOrg
    f["newbalanceOrig"] = df.newbalanceOrig
    f["oldbalanceDest"] = df.oldbalanceDest
    f["newbalanceDest"] = df.newbalanceDest

    f["orig_zero_balance"] = (df.oldbalanceOrg == 0).astype(int)
    ratio = df.amount / df.oldbalanceOrg.replace(0, np.nan)
    f["balance_drain_ratio"] = ratio.clip(upper=10).fillna(0)
    f["error_balance_orig"] = df.newbalanceOrig + df.amount - df.oldbalanceOrg
    f["error_balance_dest"] = df.oldbalanceDest + df.amount - df.newbalanceDest

    cnt, avg, gap, vel = history(df.nameOrig.to_numpy(), steps, amt)
    f["sender_prior_count"] = cnt
    f["amount_vs_user_avg"] = ratio_to_avg(df.amount, pd.Series(avg))
    f["sender_time_gap"] = pd.Series(gap).fillna(-1)
    f["sender_velocity_24h"] = vel

    pair = (df.nameOrig + ">" + df.nameDest).to_numpy()
    pcnt, _, _, _ = history(pair, steps, amt)
    f["new_recipient"] = (pcnt == 0).astype(int)

    cnt, avg, gap, vel = history(df.nameDest.to_numpy(), steps, amt)
    f["dest_prior_count"] = cnt
    f["dest_amount_vs_avg"] = ratio_to_avg(df.amount, pd.Series(avg))
    f["dest_time_gap"] = pd.Series(gap).fillna(-1)
    f["dest_velocity_24h"] = vel
    f["dest_first_time"] = (cnt == 0).astype(int)

    f["isFraud"] = df.isFraud
    return f


if __name__ == "__main__":
    feats = build()
    feats.to_parquet(OUT, index=False)
    print(feats.shape)
    print("NaN:", int(feats.isna().sum().sum()), "inf:", int(np.isinf(feats.to_numpy()).sum()))
    print(feats.describe().T[["mean", "min", "max"]])