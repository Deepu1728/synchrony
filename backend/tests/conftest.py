import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine, get_db
from app.main import app
from app.models import FraudCase


@pytest.fixture
def db():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    session.execute(delete(FraudCase).where(FraudCase.source.in_(["feedback", "reported"])))
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    if not settings.seed_admin_password:
        pytest.skip("set SEED_ADMIN_PASSWORD in .env and run scripts.seed")
    r = client.post("/auth/login", data={"username": "admin", "password": settings.seed_admin_password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    from app import llm

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    llm._calls.clear()