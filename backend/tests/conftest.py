import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine, get_db
from app.main import app


@pytest.fixture
def db():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
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