import argparse
import secrets

import bcrypt
import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import Base, engine
from app.scoring import embedding

FEATURES_PARQUET = embedding.ML_DIR / "data" / "features.parquet"
TRAIN_FRACTION = 0.6
LEGIT_SAMPLE = 20_000
BATCH = 2_000


def seed_users(db: Session) -> None:
    demo = [
        ("admin", "admin", settings.seed_admin_password),
        ("analyst", "analyst", settings.seed_analyst_password),
    ]
    for username, role, password in demo:
        if db.scalar(select(models.User).where(models.User.username == username)):
            print(f"user '{username}' exists, skipped")
            continue
        generated = not password
        password = password or secrets.token_urlsafe(12)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db.add(models.User(username=username, password_hash=hashed, role=role))
        note = f" (generated, save it now: {password})" if generated else ""
        print(f"user '{username}' created{note}")
    db.commit()


def seed_cases(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(models.FraudCase)):
        print("fraud_cases already filled, skipped (use --reset to rebuild)")
        return

    df = pd.read_parquet(FEATURES_PARQUET).sort_values("step", kind="stable").reset_index(drop=True)
    train = df.iloc[: int(len(df) * TRAIN_FRACTION)]
    embedding.fit_scaler(train)

    fraud = train[train.isFraud == 1]
    legit = train[train.isFraud == 0].sample(LEGIT_SAMPLE, random_state=42)
    cases = pd.concat([fraud.assign(label="fraud"), legit.assign(label="legit")])
    vectors = embedding.embed_frame(cases)

    rows = [
        {
            "embedding": vec.tolist(),
            "label": row.label,
            "source": "paysim_train",
            "meta": {
                "type": "TRANSFER" if row.is_transfer else "CASH_OUT",
                "amount": round(float(row.amount), 2),
                "hour": int(row.hour),
            },
        }
        for vec, row in zip(vectors, cases.itertuples())
    ]
    for i in range(0, len(rows), BATCH):
        db.execute(models.FraudCase.__table__.insert(), rows[i : i + BATCH])
    db.commit()
    print(f"fraud_cases filled: {len(fraud)} fraud + {len(legit)} legit (train split only)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    if args.reset:
        Base.metadata.drop_all(engine)
        print("dropped all tables")
    Base.metadata.create_all(engine)
    print("tables ready")

    with Session(engine) as db:
        seed_users(db)
        seed_cases(db)


if __name__ == "__main__":
    main()