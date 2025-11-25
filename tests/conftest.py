import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, timedelta, timezone

from adapt.app import create_app
from adapt.config import AdaptConfig
from adapt.storage import User, init_database
from adapt.auth.password import hash_password


@pytest.fixture(name="app")
def app_fixture(tmp_path):
    config = AdaptConfig(root=tmp_path)
    return create_app(config)


@pytest.fixture(name="client")
def client_fixture(app):
    return TestClient(app)


@pytest.fixture(name="db_session")
def db_session_fixture(app):
    engine = app.state.db_engine
    with Session(engine) as session:
        yield session


@pytest.fixture(name="superuser")
def superuser_fixture(db_session):
    user = db_session.exec(select(User).where(User.username == "admin_test")).first()
    if not user:
        user = User(username="admin_test", password_hash=hash_password("admin"), is_superuser=True)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture(name="normal_user")
def normal_user_fixture(db_session):
    user = db_session.exec(select(User).where(User.username == "user_test")).first()
    if not user:
        user = User(username="user_test", password_hash=hash_password("user"), is_superuser=False)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(client, superuser):
    response = client.post("/auth/login", data={"username": superuser.username, "password": "admin"})
    assert response.status_code == 200
    client.cookies.update(response.cookies)
    return response.cookies
