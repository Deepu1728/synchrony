import numpy as np
from sqlalchemy import select, text

from app.config import settings
from app.models import FraudCase
from app.schemas import TransactionIn
from app.scoring import embedding
from app.scoring.features import build_features
from app.scoring.similarity import find_neighbours

PROBES = [
    dict(step=4, type="TRANSFER", amount=692654.27, name_orig="C11", oldbalance_org=692654.27, newbalance_orig=0,
         name_dest="C12", oldbalance_dest=0, newbalance_dest=0),
    dict(step=14, type="CASH_OUT", amount=8500, name_orig="C13", oldbalance_org=20632, newbalance_orig=12132,
         name_dest="C14", oldbalance_dest=21182, newbalance_dest=29682),
    dict(step=372, type="TRANSFER", amount=185829, name_orig="C15", oldbalance_org=5464727, newbalance_orig=5278898,
         name_dest="C16", oldbalance_dest=0, newbalance_dest=185829),
    dict(step=372, type="TRANSFER", amount=1721379, name_orig="C17", oldbalance_org=5464727, newbalance_orig=3743348,
         name_dest="C18", oldbalance_dest=0, newbalance_dest=0),
    dict(step=400, type="CASH_OUT", amount=250000, name_orig="C19", oldbalance_org=900000, newbalance_orig=650000,
         name_dest="C20", oldbalance_dest=10000, newbalance_dest=260000),
    dict(step=500, type="CASH_OUT", amount=64000, name_orig="C21", oldbalance_org=64000, newbalance_orig=0,
         name_dest="C22", oldbalance_dest=0, newbalance_dest=64000),
]


def test_neighbour_search_is_exact_and_ignores_the_index(db):
    assert settings.similarity_exact is True
    cases = db.execute(select(FraudCase.label, FraudCase.embedding)).all()
    vectors = np.array([np.asarray(c.embedding, dtype=np.float64) for c in cases])
    labels = np.array([c.label for c in cases])
    checked = 0
    for probe in PROBES:
        features = build_features(db, TransactionIn(**probe))
        query = np.asarray(embedding.embed_one(features), dtype=np.float64)
        distances = np.linalg.norm(vectors - query, axis=1)
        order = np.argsort(distances)
        k = settings.similarity_k
        if distances[order[k]] - distances[order[k - 1]] < 1e-3:
            continue
        expected = int((labels[order[:k]] == "fraud").sum())
        assert find_neighbours(db, features).fraud == expected
        checked += 1
    assert checked >= 4


def test_exact_search_does_not_leave_index_scans_disabled(db):
    features = build_features(db, TransactionIn(**PROBES[1]))
    find_neighbours(db, features)
    assert db.execute(text("SHOW enable_indexscan")).scalar() == "on"
    assert db.execute(text("SHOW enable_bitmapscan")).scalar() == "on"
