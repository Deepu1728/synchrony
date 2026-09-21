import argparse
import random
import sys
from dataclasses import dataclass, field

from app.config import settings

FAMILIES = ("original", "structuring", "partial_drain", "daytime", "aged_mule", "combo")
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
    from scripts import simulate

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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Show example red-team fraud variants built from real held-out fraud rows")
    p.add_argument("--families", nargs="+", default=list(FAMILIES), help=f"any of {FAMILIES}")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)
    unknown = [f for f in args.families if f not in FAMILIES]
    if unknown:
        p.error(f"unknown families: {unknown}")

    print("loading held-out fraud rows...")
    rows = real_fraud_rows(args.seed)
    rng, ids = random.Random(args.seed), IdFactory(start=args.seed * 10_000_000)
    print(f"{len(rows)} real fraud rows (PaySim test period)\n")
    for family in args.families:
        row = next(r for r in rows if family != "structuring" or r.oldbalanceOrg >= STRUCTURING_MIN_BALANCE)
        print(f"real fraud row: step {row.step} {row.type} amount {row.amount:,.2f} victim balance {row.oldbalanceOrg:,.2f}")
        print(show(make_scenario(family, row, rng, ids)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())