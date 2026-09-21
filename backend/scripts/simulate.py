import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from app.config import settings
from app.scoring.embedding import ML_DIR

RAW = ML_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
TYPES = ["TRANSFER", "CASH_OUT"]
USECOLS = ["step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
           "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud"]


class SimulationAborted(Exception):
    pass


def load_stream(csv_path=RAW, test_fraction: float = 0.8) -> pd.DataFrame:
    df = pd.read_csv(csv_path, usecols=USECOLS)
    df = df[df.type.isin(TYPES)].sort_values("step", kind="stable").reset_index(drop=True)
    return df.iloc[int(len(df) * test_fraction):].reset_index(drop=True)


def pick(stream: pd.DataFrame, start: int, limit: int, fraud_share: float | None, seed: int = 42) -> pd.DataFrame:
    window = stream.iloc[start:]
    if not fraud_share:
        return window.head(limit)
    n_fraud = max(1, round(limit * fraud_share))
    fraud_idx = window.index[window.isFraud == 1][:n_fraud]
    if len(fraud_idx) == 0:
        return window.head(limit)
    upto = window.loc[: fraud_idx[-1]]
    genuine = upto[upto.isFraud == 0]
    keep = genuine.sample(min(len(genuine), limit - len(fraud_idx)), random_state=seed).index
    return window.loc[sorted(set(fraud_idx) | set(keep))]


def to_payload(row) -> dict:
    return {
        "step": int(row.step), "type": row.type, "amount": float(row.amount),
        "name_orig": row.nameOrig, "oldbalance_org": float(row.oldbalanceOrg),
        "newbalance_orig": float(row.newbalanceOrig), "name_dest": row.nameDest,
        "oldbalance_dest": float(row.oldbalanceDest), "newbalance_dest": float(row.newbalanceDest),
        "true_label": bool(row.isFraud),
    }


def _ratio(a: int, b: int):
    return round(a / b, 4) if b else None


def _pct(values: list[float], q: int):
    return round(float(np.percentile(values, q)), 1) if values else None


class Stats:
    def __init__(self):
        self.fraud, self.genuine = Counter(), Counter()
        self.errors, self.feedback = Counter(), Counter()
        self.client_ms: list[float] = []
        self.server_ms: list[float] = []

    def record(self, is_fraud: bool, decision: str, client_ms: float, server_ms: float) -> None:
        (self.fraud if is_fraud else self.genuine)[decision] += 1
        self.client_ms.append(client_ms)
        self.server_ms.append(server_ms)

    def summary(self, elapsed: float) -> dict:
        f, g = self.fraud, self.genuine
        fraud_total, genuine_total = sum(f.values()), sum(g.values())
        flagged_f, flagged_g = f["block"] + f["review"], g["block"] + g["review"]
        sent = fraud_total + genuine_total
        return {
            "sent": sent,
            "elapsed_s": round(elapsed, 1),
            "throughput_tps": round(sent / elapsed, 1) if elapsed else 0,
            "latency_ms": {
                "client_p50": _pct(self.client_ms, 50), "client_p95": _pct(self.client_ms, 95),
                "server_p50": _pct(self.server_ms, 50), "server_p95": _pct(self.server_ms, 95),
            },
            "fraud": {"total": fraud_total, "blocked": f["block"], "review": f["review"], "missed": f["approve"]},
            "genuine": {"total": genuine_total, "blocked": g["block"], "review": g["review"], "approved": g["approve"]},
            "recall_block": _ratio(f["block"], fraud_total),
            "recall_flagged": _ratio(flagged_f, fraud_total),
            "precision_block": _ratio(f["block"], f["block"] + g["block"]),
            "precision_flagged": _ratio(flagged_f, flagged_f + flagged_g),
            "stream_fraud_share": _ratio(fraud_total, sent),
            "errors": dict(self.errors),
            "feedback": dict(self.feedback),
        }


def live_line(s: dict) -> str:
    f, g = s["fraud"], s["genuine"]
    return (f"t={s['elapsed_s']:>6.1f}s sent={s['sent']:>6} {s['throughput_tps']:>5.1f}/s "
            f"lat p50={s['latency_ms']['client_p50']}ms p95={s['latency_ms']['client_p95']}ms | "
            f"fraud {f['total']}: blocked {f['blocked']} review {f['review']} MISSED {f['missed']} | "
            f"genuine {g['total']}: blocked {g['blocked']} review {g['review']}")


def replay(http, rows: pd.DataFrame, rate: float = 0.0, every: float = 5.0, feedback: float = 0.0,
           seed: int = 1, relogin=None, deadline: float | None = None, out=print) -> Stats:
    stats, rng = Stats(), random.Random(seed)
    started = last_print = time.perf_counter()
    failures, shown = 0, 0

    for i, row in enumerate(rows.itertuples(index=False)):
        now = time.perf_counter()
        if deadline and now >= deadline:
            out("duration reached, stopping")
            break
        if rate > 0 and (wait := started + i / rate - now) > 0:
            time.sleep(wait)

        payload = to_payload(row)
        t0 = time.perf_counter()
        try:
            resp = http.post("/score", json=payload)
            if resp.status_code == 401 and relogin:
                relogin()
                resp = http.post("/score", json=payload)
        except httpx.HTTPError as exc:
            stats.errors["connection"] += 1
            failures += 1
            if failures >= 5:
                raise SimulationAborted(f"server unreachable ({exc.__class__.__name__})") from exc
            continue
        client_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code == 422:
            stats.errors["rejected"] += 1
            if shown < 3:
                out(f"rejected by validation: {resp.json()['detail'][0]['msg']}")
                shown += 1
        elif resp.status_code != 200:
            stats.errors[f"http_{resp.status_code}"] += 1
            failures += 1
            if failures >= 5:
                raise SimulationAborted(f"server keeps failing (HTTP {resp.status_code})")
        else:
            failures = 0
            body = resp.json()
            stats.record(payload["true_label"], body["decision"], client_ms, body["latency_ms"])
            if feedback and body["alert_id"] and rng.random() < feedback:
                verdict = "fraud" if payload["true_label"] else "legit"
                r = http.post("/feedback", json={"alert_id": body["alert_id"], "verdict": verdict,
                                                 "note": "simulated analyst"})
                stats.feedback[f"{verdict}_{r.status_code}"] += 1

        if time.perf_counter() - last_print >= every:
            out(live_line(stats.summary(time.perf_counter() - started)))
            last_print = time.perf_counter()

    return stats


def login(http, username: str, password: str) -> str:
    r = http.post("/auth/login", data={"username": username, "password": password})
    if r.status_code != 200:
        raise SimulationAborted(f"login failed (HTTP {r.status_code}); check --username/--password "
                                f"or SEED_ADMIN_PASSWORD in .env")
    return r.json()["access_token"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Replay PaySim test-period transactions into /score")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default=settings.seed_admin_password)
    p.add_argument("--limit", type=int, default=2000, help="max transactions to send")
    p.add_argument("--start", type=int, default=0, help="offset into the test-period stream")
    p.add_argument("--rate", type=float, default=20.0, help="transactions per second (0 = as fast as possible)")
    p.add_argument("--duration", type=float, default=0.0, help="stop after N seconds (0 = no limit)")
    p.add_argument("--fraud-share", type=float, default=0.0,
                   help="oversample fraud to this share of the stream, e.g. 0.05 (0 = natural mix)")
    p.add_argument("--feedback", type=float, default=0.0,
                   help="fraction of alerts a simulated analyst reviews immediately, e.g. 0.5")
    p.add_argument("--every", type=float, default=5.0, help="seconds between live stat lines")
    p.add_argument("--report", type=Path, default=None, help="write the final summary as JSON")
    args = p.parse_args(argv)

    print("loading PaySim test-period stream...")
    rows = pick(load_stream(), args.start, args.limit, args.fraud_share or None)
    fraud_n = int(rows.isFraud.sum())
    print(f"stream: {len(rows)} transactions ({fraud_n} fraud, {len(rows) - fraud_n} genuine), "
          f"rate {args.rate or 'max'}/s, target {args.base_url}")

    started = time.perf_counter()
    try:
        with httpx.Client(base_url=args.base_url, timeout=30) as http:
            def relogin():
                http.headers["Authorization"] = f"Bearer {login(http, args.username, args.password)}"

            try:
                relogin()
            except httpx.ConnectError:
                raise SimulationAborted(f"cannot reach {args.base_url}; start the API first "
                                        f"(uvicorn app.main:app --port 8000)")
            deadline = started + args.duration if args.duration else None
            try:
                stats = replay(http, rows, args.rate, args.every, args.feedback, relogin=relogin, deadline=deadline)
            except KeyboardInterrupt:
                print("\ninterrupted")
                return 130
            open_alerts = http.get("/alerts", params={"status": "open", "limit": 1}).json()["total"]
            all_alerts = http.get("/alerts", params={"limit": 1}).json()["total"]
    except SimulationAborted as exc:
        print(f"error: {exc}")
        return 2

    summary = stats.summary(time.perf_counter() - started)
    summary["alerts_total"], summary["alerts_open"] = all_alerts, open_alerts
    print("\n=== summary ===")
    print(json.dumps(summary, indent=2))
    if args.report:
        args.report.write_text(json.dumps(summary, indent=2))
        print(f"report written to {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())