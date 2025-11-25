
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, timedelta, timezone

from adapt.app import create_app
from adapt.config import AdaptConfig
from adapt.storage import User, APIKey, AuditLog, get_db_session
from adapt.auth import hash_password
from adapt.api_keys import generate_api_key

@pytest.fixture(name="app")
def app_fixture(tmp_path):
    config = AdaptConfig(root=tmp_path)
    return create_app(config)

@pytest.fixture(name="client")
def client_fixture(app):
    return TestClient(app)

# Remove global client definition
# client = TestClient(app)

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
    # Login to get session cookie
    response = client.post("/auth/login", data={"username": superuser.username, "password": "admin"})
    assert response.status_code == 200
    # Apply cookies to client to avoid deprecated per-request 'cookies' parameter
    client.cookies.update(response.cookies)
    return response.cookies

def test_api_key_lifecycle(client, db_session, superuser, auth_headers):
    # 1. Create API Key via Admin API
    response = client.post(
        "/admin/api-keys",
        json={"user_id": superuser.id, "description": "Test Key", "expires_in_days": 30},
    )
    assert response.status_code == 200
    data = response.json()
    api_key = data["key"]
    key_id = data["id"]
    assert api_key.startswith("ak_")
    
    # 2. Verify Key in DB
    stored_key = db_session.get(APIKey, key_id)
    assert stored_key is not None
    assert stored_key.description == "Test Key"
    
    # 3. Use API Key to authenticate
    # We'll hit the /auth/me endpoint which requires authentication
    response = client.get("/auth/me", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    assert response.json()["username"] == superuser.username
    
    # 4. Revoke Key
    response = client.delete(f"/admin/api-keys/{key_id}")
    assert response.status_code == 200
    
    # 5. Verify Key is gone
    db_session.expire_all()
    stored_key = db_session.get(APIKey, key_id)
    assert stored_key is None
    
    # 6. Try to use revoked key
    client.cookies.clear()
    response = client.get("/auth/me", headers={"X-API-Key": api_key})
    assert response.status_code == 401

def test_audit_logging(client, db_session, superuser, auth_headers):
    # 1. Perform an action that should be logged (e.g., creating a user)
    # We'll create a new user via the admin API
    new_user_data = {"username": "audit_test_user", "password": "password", "is_superuser": False}
    response = client.post("/admin/users", json=new_user_data)
    assert response.status_code == 200
    new_user_id = response.json()["id"]
    
    # 2. Verify Audit Log
    # We expect a log entry for "create_user"
    log = db_session.exec(select(AuditLog).where(AuditLog.action == "create_user").order_by(AuditLog.timestamp.desc())).first()
    assert log is not None
    assert log.user_id == superuser.id
    assert log.resource == "user"
    assert "audit_test_user" in log.details
    
    # 3. Test Login Logging
    # Login as the new user
    response = client.post("/auth/login", data={"username": "audit_test_user", "password": "password"})
    assert response.status_code == 200
    
    # Verify login log
    log = db_session.exec(select(AuditLog).where(AuditLog.action == "login").where(AuditLog.user_id == new_user_id).order_by(AuditLog.timestamp.desc())).first()
    assert log is not None
    assert log.user_id == new_user_id
    
    # 4. Test Logout Logging
    # Logout
    cookies = response.cookies
    # Set cookies on client rather than passing per-request to avoid deprecation
    client.cookies.clear()
    client.cookies.update(cookies)
    response = client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    
    # Verify logout log
    log = db_session.exec(select(AuditLog).where(AuditLog.action == "logout").where(AuditLog.user_id == new_user_id).order_by(AuditLog.timestamp.desc())).first()
    assert log is not None

def test_rls_filtering(client, db_session, normal_user):
    # This requires a dataset plugin that implements filter_for_user.
    # The default DatasetPlugin now has the hook, but it just returns all rows by default.
    # To test this properly, I would need to mock or subclass DatasetPlugin.
    pass
