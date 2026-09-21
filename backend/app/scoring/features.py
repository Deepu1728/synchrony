from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import TransactionIn

WINDOW = 24

_HISTORY_SQL = {
    "orig": text(
        "SELECT count(*), avg(amount), max(step), count(*) FILTER (WHERE step >= :lo) "
        "FROM transactions WHERE name_orig = :key AND step <= :step"
    ),
    "dest": text(
        "SELECT count(*), avg(amount), max(step), count(*) FILTER (WHERE step >= :lo) "
        "FROM transactions WHERE name_dest = :key AND step <= :step"
    ),
}
_PAIR_SQL = text(
    "SELECT count(*) FROM transactions "
    "WHERE name_orig = :orig AND name_dest = :dest AND step <= :step"
)


def _history(db: Session, side: str, key: str, step: int) -> dict:
    count, avg, last_step, in_window = db.execute(
        _HISTORY_SQL[side], {"key": key, "step": step, "lo": step - WINDOW}
    ).one()
    return {
        "count": int(count),
        "avg": float(avg) if avg is not None else None,
        "gap": step - int(last_step) if count else -1,
        "velocity": int(in_window),
    }


def _ratio_to_avg(amount: float, avg: float | None) -> float:
    if avg is None or avg <= 0:
        return 1.0
    return min(amount / avg, 1000.0)


def build_features(db: Session, txn: TransactionIn) -> dict:
    ratio = txn.amount / txn.oldbalance_org if txn.oldbalance_org > 0 else 0.0
    sender = _history(db, "orig", txn.name_orig, txn.step)
    receiver = _history(db, "dest", txn.name_dest, txn.step)
    pair_count = db.execute(
        _PAIR_SQL, {"orig": txn.name_orig, "dest": txn.name_dest, "step": txn.step}
    ).scalar_one()

    return {
        "hour": txn.step % 24,
        "is_transfer": int(txn.type == "TRANSFER"),
        "amount": txn.amount,
        "oldbalanceOrg": txn.oldbalance_org,
        "newbalanceOrig": txn.newbalance_orig,
        "oldbalanceDest": txn.oldbalance_dest,
        "newbalanceDest": txn.newbalance_dest,
        "orig_zero_balance": int(txn.oldbalance_org == 0),
        "balance_drain_ratio": min(ratio, 10.0),
        "error_balance_orig": txn.newbalance_orig + txn.amount - txn.oldbalance_org,
        "error_balance_dest": txn.oldbalance_dest + txn.amount - txn.newbalance_dest,
        "sender_prior_count": sender["count"],
        "amount_vs_user_avg": _ratio_to_avg(txn.amount, sender["avg"]),
        "sender_time_gap": sender["gap"],
        "sender_velocity_24h": sender["velocity"],
        "new_recipient": int(pair_count == 0),
        "dest_prior_count": receiver["count"],
        "dest_amount_vs_avg": _ratio_to_avg(txn.amount, receiver["avg"]),
        "dest_time_gap": receiver["gap"],
        "dest_velocity_24h": receiver["velocity"],
        "dest_first_time": int(receiver["count"] == 0),
    }