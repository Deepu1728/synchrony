import argparse
import json
import random
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pandas as pd

from app.config import settings
from scripts import simulate

FAMILIES = ("original", "structuring", "partial_drain", "daytime", "aged_mule", "combo")
DEFAULT_FAMILIES = ("structuring", "partial_drain", "combo", "aged_mule")
STRUCTURING_MIN_BALANCE = 2 * settings.rule_high_amount
MAX_PARTS = 8


class IdFactory:
    def __init__(self, start: int = 0):
        self.n = start

    def next(self, prefix: str) -> str:
        self.n += 1
        return f"C{prefix}{self.n:09d}"


@dataclass
class Scenario:
    family: str
    grooming: list[dict] = field(default_factory=list)
    attack: list[dict] = field(default_factory=list)


def _txn(step, kind, amount, orig, old_orig, dest, old_dest, new_dest, label):
    amount = round(float(amount), 2)
    return {
        "step": max(1, int(step)), "type": kind, "amount": amount,
        "name_orig": orig, "oldbalance_org": round(float(old_orig), 2),
        "newbalance_orig": round(max(float(old_orig) - amount, 0.0), 2),
        "name_dest": dest, "oldbalance_dest": round(float(old_dest), 2),
        "newbalance_dest": round(float(new_dest), 2), "true_label": label,
    }


def _dest_after(row, amount: float, old_dest: float) -> float:
    return old_dest if row.newbalanceDest == row.oldbalanceDest else old_dest + amount


def _groom(mule: str, before_step: int, rng: random.Random, ids: IdFactory) -> tuple[list[dict], float]:
    txns, balance = [], 0.0
    for k in range(4):
        amount = rng.uniform(3_000, 25_000)
        txns.append(_txn(before_step - 40 + k * 8, "CASH_OUT", amount, ids.next("97"), amount * 3,
                         mule, balance, balance + amount, False))
        balance += amount
    return txns, balance


def _daytime_step(step: int, rng: random.Random) -> int:
    return max(1, step - step % 24 + rng.randint(10, 17))


def make_scenario(family: str, row, rng: random.Random, ids: IdFactory) -> Scenario:
    victim, mule = ids.next("99"), ids.next("98")
    balance, old_dest, step = float(row.oldbalanceOrg), float(row.oldbalanceDest), int(row.step)
    sc = Scenario(family)

    if family == "original":
        sc.attack = [{
            "step": step, "type": row.type, "amount": float(row.amount), "name_orig": victim,
            "oldbalance_org": balance, "newbalance_orig": float(row.newbalanceOrig), "name_dest": mule,
            "oldbalance_dest": old_dest, "newbalance_dest": float(row.newbalanceDest), "true_label": True,
        }]
    elif family == "structuring":
        remaining, part = balance, 0
        while remaining > 0.01 and part < MAX_PARTS:
            amount = min(remaining, settings.rule_high_amount * rng.uniform(0.90, 0.99))
            new_dest = _dest_after(row, amount, old_dest)
            sc.attack.append(_txn(step + part, row.type, amount, victim, remaining, mule, old_dest, new_dest, True))
            remaining -= amount
            old_dest = new_dest
            part += 1
    elif family == "partial_drain":
        amount = balance * rng.uniform(0.3, 0.7)
        sc.attack = [_txn(step, row.type, amount, victim, balance, mule, old_dest,
                          _dest_after(row, amount, old_dest), True)]
    elif family == "daytime":
        amount = float(row.amount)
        sc.attack = [_txn(_daytime_step(step, rng), row.type, amount, victim, balance, mule, old_dest,
                          _dest_after(row, amount, old_dest), True)]
    elif family in ("aged_mule", "combo"):
        step = _daytime_step(step, rng) if family == "combo" else step
        amount = float(row.amount) if family == "aged_mule" else balance * rng.uniform(0.3, 0.7)
        sc.grooming, mule_balance = _groom(mule, step, rng, ids)
        sc.attack = [_txn(step, row.type, amount, victim, balance, mule, mule_balance, mule_balance + amount, True)]
    else:
        raise ValueError(f"unknown family: {family}")
    return sc


def real_fraud_rows(seed: int = 7) -> list:
    stream = simulate.load_stream()
    fraud = stream[stream.isFraud == 1].sample(frac=1, random_state=seed)
    return list(fraud.itertuples(index=False))


def show(sc: Scenario) -> str:
    lines = [f"--- {sc.family}: {len(sc.attack)} attack transaction(s), {len(sc.grooming)} grooming"]
    for label, txns in (("groom", sc.grooming), ("ATTACK", sc.attack)):
        for t in txns:
            lines.append(
                f"  {label:<6} step {t['step']:>3} (hour {t['step'] % 24:>2}) {t['type']:<8} {t['amount']:>12,.2f}  "
                f"{t['name_orig']} balance {t['oldbalance_org']:>12,.2f} -> {t['newbalance_orig']:>12,.2f}  to {t['name_dest']}"
            )
    return "\n".join(lines)


def _score(http, payload: dict) -> dict:
    r = http.post("/score", json=payload)
    if r.status_code != 200:
        raise simulate.SimulationAborted(f"/score failed (HTTP {r.status_code}): {r.text[:200]}")
    return r.json()


def _label_fraud(http, body: dict) -> None:
    if body["alert_id"]:
        r = http.post("/feedback", json={"alert_id": body["alert_id"], "verdict": "fraud", "note": "red-team"})
    else:
        r = http.post(f"/transactions/{body['transaction_id']}/report-fraud", json={"note": "red-team"})
    if r.status_code != 201:
        raise simulate.SimulationAborted(f"labelling failed (HTTP {r.status_code}): {r.text[:200]}")


def summarize(decisions: list[str], lost: float, intended: float, labelled: int = 0) -> dict:
    n = len(decisions)
    return {
        "txns": n,
        "flagged_rate": round(sum(d != "approve" for d in decisions) / n, 4) if n else None,
        "blocked_rate": round(sum(d == "block" for d in decisions) / n, 4) if n else None,
        "money_lost_share": round(lost / intended, 4) if intended else None,
        "labelled": labelled,
    }


def run_phase(http, scenarios: list[Scenario], learn: bool = False) -> dict:
    decisions, lost, intended, labelled = [], 0.0, 0.0, 0
    for sc in scenarios:
        for txn in sc.grooming:
            _score(http, txn)
        stopped = False
        for txn in sc.attack:
            body = _score(http, txn)
            decisions.append(body["decision"])
            intended += txn["amount"]
            if not stopped:
                if body["decision"] == "approve":
                    lost += txn["amount"]
                else:
                    stopped = True
            if learn:
                _label_fraud(http, body)
                labelled += 1
    return summarize(decisions, lost, intended, labelled)


def false_alarms(http, rows: pd.DataFrame) -> int:
    flagged = 0
    for row in rows.itertuples(index=False):
        payload = {**simulate.to_payload(row), "true_label": False}
        r = http.post("/score/preview", json=payload)
        if r.status_code != 200:
            raise simulate.SimulationAborted(f"/score/preview failed (HTTP {r.status_code}): {r.text[:200]}")
        flagged += r.json()["decision"] != "approve"
    return flagged


def run_family(http, family: str, pool: list, genuine: pd.DataFrame, n_eval: int, n_learn: int,
               rng: random.Random, ids: IdFactory) -> dict:
    rows = [r for r in pool if family != "structuring" or r.oldbalanceOrg >= STRUCTURING_MIN_BALANCE]
    need = 2 * n_eval + n_learn
    if len(rows) < need:
        raise simulate.SimulationAborted(f"{family}: need {need} fraud rows, only {len(rows)} available")
    eval_before = [make_scenario(family, r, rng, ids) for r in rows[:n_eval]]
    learn = [make_scenario(family, r, rng, ids) for r in rows[n_eval:n_eval + n_learn]]
    eval_after = [make_scenario(family, r, rng, ids) for r in rows[n_eval + n_learn:need]]

    genuine_before = false_alarms(http, genuine)
    before = run_phase(http, eval_before)
    learned = run_phase(http, learn, learn=True)
    after = run_phase(http, eval_after)
    genuine_after = false_alarms(http, genuine)
    return {"family": family, "before": before, "learned_labels": learned["labelled"], "after": after,
            "genuine_false_alarms": {"rows": len(genuine), "before": genuine_before, "after": genuine_after}}


@contextmanager
def in_process_client(username: str, password: str):
    from fastapi.testclient import TestClient
    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    from app.db import engine, get_db
    from app.main import app
    from app.models import FraudCase

    connection = engine.connect()
    outer = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    db.execute(delete(FraudCase).where(FraudCase.source.in_(["feedback", "reported"])))
    app.dependency_overrides[get_db] = lambda: db
    try:
        http = TestClient(app)
        http.headers["Authorization"] = f"Bearer {simulate.login(http, username, password)}"
        yield http
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        outer.rollback()
        connection.close()


@contextmanager
def live_client(base_url: str, username: str, password: str):
    with httpx.Client(base_url=base_url, timeout=60) as http:
        http.headers["Authorization"] = f"Bearer {simulate.login(http, username, password)}"
        yield http


def _pct(value) -> str:
    return "  n/a" if value is None else f"{value * 100:5.1f}%"


def format_table(results: list[dict]) -> str:
    lines = [f"{'family':<14} {'flagged':>15} {'blocked':>15} {'money lost':>15} {'genuine flagged (same rows)':>34}",
             f"{'':<14} {'before>after':>15} {'before>after':>15} {'before>after':>15} {'before > after':>34}"]
    for r in results:
        b, a, g = r["before"], r["after"], r["genuine_false_alarms"]
        lines.append(
            f"{r['family']:<14} {_pct(b['flagged_rate'])}>{_pct(a['flagged_rate'])} "
            f"{_pct(b['blocked_rate'])}>{_pct(a['blocked_rate'])} "
            f"{_pct(b['money_lost_share'])}>{_pct(a['money_lost_share'])} "
            f"{g['before']:>10d} > {g['after']:<4d} (of {g['rows']})"
        )
    return "\n".join(lines)


def plot_results(results: list[dict], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [r["family"] for r in results]
    panels = [
        ("Fraud transactions flagged\n(higher is better)", lambda r, k: (r[k]["flagged_rate"] or 0) * 100, "%"),
        ("Stolen money that got through\n(lower is better)", lambda r, k: (r[k]["money_lost_share"] or 0) * 100, "%"),
        ("Genuine transactions flagged\n(same rows, lower is better)",
         lambda r, k: 100 * r["genuine_false_alarms"][k] / max(r["genuine_false_alarms"]["rows"], 1), "%"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, (title, value, unit) in zip(axes, panels):
        x = range(len(names))
        ax.bar([i - 0.2 for i in x], [value(r, "before") for r in results], 0.4, label="before learning", color="#c44e52")
        ax.bar([i + 0.2 for i in x], [value(r, "after") for r in results], 0.4, label="after learning", color="#4c72b0")
        ax.set_xticks(list(x), names, rotation=15)
        ax.set_ylabel(unit)
        ax.set_title(title, fontsize=10)
        ax.legend()
    axes[0].set_ylim(0, 105)
    axes[1].set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Red-team the fraud system with evasive fraud variants and measure learning")
    p.add_argument("--families", nargs="+", default=list(DEFAULT_FAMILIES), help=f"any of {FAMILIES} or 'all'")
    p.add_argument("--scenarios", type=int, default=40, help="attack scenarios per before/after phase")
    p.add_argument("--learn", type=int, default=15, help="scenarios the analysts label between the phases")
    p.add_argument("--genuine", type=int, default=2000, help="genuine transactions re-scored read-only before and after learning")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--base-url", default=None, help="score against a running API and keep the data; default is a dry run that is rolled back")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default=settings.seed_admin_password)
    p.add_argument("--show", action="store_true", help="only print one example of each variant and exit")
    p.add_argument("--report", type=Path, default=None, help="write results as JSON")
    p.add_argument("--plot", type=Path, default=None, help="write a before/after chart (PNG)")
    args = p.parse_args(argv)
    families = list(FAMILIES) if args.families == ["all"] else args.families
    unknown = [f for f in families if f not in FAMILIES]
    if unknown:
        p.error(f"unknown families: {unknown}")

    print("loading PaySim test-period stream...")
    stream = simulate.load_stream()
    fraud = stream[stream.isFraud == 1].sample(frac=1, random_state=args.seed)
    genuine = stream[stream.isFraud == 0].sample(args.genuine, random_state=args.seed + 1)
    pool = list(fraud.itertuples(index=False))
    rng, ids = random.Random(args.seed), IdFactory(start=args.seed * 10_000_000)

    if args.show:
        for family in families:
            row = next(r for r in pool if family != "structuring" or r.oldbalanceOrg >= STRUCTURING_MIN_BALANCE)
            print(f"real fraud row: step {row.step} {row.type} amount {row.amount:,.2f} victim balance {row.oldbalanceOrg:,.2f}")
            print(show(make_scenario(family, row, rng, ids)) + "\n")
        return 0

    live = args.base_url is not None
    print(f"mode: {'LIVE against ' + args.base_url + ' (data is kept, learning accumulates across families)' if live else 'dry run (in-process, rolled back)'}")

    results = []
    try:
        for family in families:
            print(f"running {family}...", flush=True)
            opener = live_client(args.base_url, args.username, args.password) if live \
                else in_process_client(args.username, args.password)
            with opener as http:
                results.append(run_family(http, family, pool, genuine, args.scenarios, args.learn, rng, ids))
    except simulate.SimulationAborted as exc:
        print(f"error: {exc}")
        return 2
    except httpx.ConnectError:
        print(f"error: cannot reach {args.base_url}")
        return 2

    print("\n" + format_table(results))
    payload = {"scenarios_per_phase": args.scenarios, "learn_scenarios": args.learn,
               "genuine_per_check": args.genuine, "seed": args.seed, "results": results}
    if args.report:
        args.report.write_text(json.dumps(payload, indent=2))
        print(f"\nreport written to {args.report}")
    if args.plot:
        plot_results(results, args.plot)
        print(f"chart written to {args.plot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())