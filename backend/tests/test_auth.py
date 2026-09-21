from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

pytestmark = pytest.mark.skipif(
    not (settings.seed_admin_password and settings.seed_analyst_password),
    reason="set SEED_ADMIN_PASSWORD and SEED_ANALYST_PASSWORD in .env and run scripts.seed",
)

client = TestClient(app)

GOOD_TXN = {
    "step": 10,
    "type": "TRANSFER",
    "amount": 1500.5,
    "name_orig": "C1231006815",
    "oldbalance_org": 1500.5,
    "newbalance_orig": 0.0,
    "name_dest": "C553264065",
    "oldbalance_dest": 0.0,
    "newbalance_dest": 0.0,
}


def login(username="admin", password=None):
    password = password if password is not None else settings.seed_admin_password
    return client.post("/auth/login", data={"username": username, "password": password})


def auth_header(token=None):
    return {"Authorization": f"Bearer {token or login().json()['access_token']}"}


def test_health_is_public():
    assert client.get("/health").status_code == 200


def test_login_returns_token_with_role_and_expiry():
    r = login()
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_expire_minutes * 60
    claims = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert claims["sub"] == "admin" and claims["role"] == "admin" and "exp" in claims


def test_analyst_role_claim():
    r = login("analyst", settings.seed_analyst_password)
    claims = jwt.decode(r.json()["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert claims["role"] == "analyst"


def test_wrong_password_and_unknown_user_same_error():
    a = login(password="wrong-password")
    b = login("nobody", "whatever")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_very_long_password_is_rejected_not_crashing():
    assert login(password="x" * 500).status_code == 401


def test_me_requires_token():
    assert client.get("/auth/me").status_code == 401
    r = client.get("/auth/me", headers=auth_header())
    assert r.status_code == 200 and r.json() == {"username": "admin", "role": "admin"}


def test_score_without_token_is_401():
    assert client.post("/score", json=GOOD_TXN).status_code == 401


def test_garbage_token_is_401():
    assert client.post("/score", json=GOOD_TXN, headers=auth_header("not.a.token")).status_code == 401


def test_expired_token_is_401():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "admin", "role": "admin", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.post("/score", json=GOOD_TXN, headers=auth_header(token)).status_code == 401


def test_token_signed_with_other_secret_is_401():
    token = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "x" * 40,
        algorithm=settings.jwt_algorithm,
    )
    assert client.post("/score", json=GOOD_TXN, headers=auth_header(token)).status_code == 401


def test_token_for_deleted_user_is_401():
    token = jwt.encode(
        {"sub": "ghost", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.post("/score", json=GOOD_TXN, headers=auth_header(token)).status_code == 401


def test_good_payload_is_accepted():
    r = client.post("/score", json=GOOD_TXN, headers=auth_header())
    assert r.status_code == 200 and r.json()["validated"] is True


@pytest.mark.parametrize(
    "patch",
    [
        {"amount": -1},
        {"amount": "abc"},
        {"type": "PAYMENT"},
        {"name_orig": "X123"},
        {"name_dest": "C1; DROP TABLE users"},
        {"step": 0},
        {"oldbalance_org": -5},
        {"amount": 1e15},
        {"name_dest": "C1231006815"},
        {"unexpected_field": 1},
    ],
)
def test_bad_payload_is_422(patch):
    r = client.post("/score", json={**GOOD_TXN, **patch}, headers=auth_header())
    assert r.status_code == 422


def test_missing_field_is_422():
    bad = {k: v for k, v in GOOD_TXN.items() if k != "amount"}
    assert client.post("/score", json=bad, headers=auth_header()).status_code == 422