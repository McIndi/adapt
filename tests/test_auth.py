import pytest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from adapt.auth.session import get_session, create_session, SESSION_TTL
from adapt.storage import User, DBSession, APIKey, init_database
from adapt.config import AdaptConfig
import tempfile
import os
from pathlib import Path


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = init_database(db_path)
    with Session(engine) as session:
        yield session
    engine.dispose()  # Clean up engine


def test_get_session_expired(db_session):
    # Create a user
    user = User(username="test", password_hash="dummy", is_active=True, is_superuser=False)
    db_session.add(user)
    db_session.commit()

    # Create an expired session
    expired_time = datetime.now(tz=timezone.utc) - timedelta(days=1)
    expired_session = DBSession(
        user_id=user.id,
        token="expired_token",
        created_at=expired_time,
        expires_at=expired_time,
        last_active=expired_time,
    )
    db_session.add(expired_session)
    db_session.commit()

    # Act
    result = get_session(db_session, "expired_token")

    # Assert
    assert result is None


def test_get_session_valid(db_session):
    # Create a user
    user = User(username="test", password_hash="dummy", is_active=True, is_superuser=False)
    db_session.add(user)
    db_session.commit()

    # Create a valid session
    token = create_session(db_session, user.id)

    # Capture existing expires_at
    from sqlmodel import select
    initial = db_session.exec(select(DBSession).where(DBSession.token == token)).first()
    old_expires_at = initial.expires_at

    # Act
    result = get_session(db_session, token)

    # Assert
    assert result is not None
    assert result.token == token
    assert result.user_id == user.id
    # Check that last_active was updated (sliding expiration)
    assert result.last_active > result.created_at
    # Check that expires_at was extended
    assert result.expires_at > old_expires_at


def test_get_session_nonexistent(db_session):
    # Act
    result = get_session(db_session, "nonexistent_token")

    # Assert
    assert result is None


def test_session_expiration_enforced(db_session):
    # Create a user
    user = User(username="test", password_hash="dummy", is_active=True, is_superuser=False)
    db_session.add(user)
    db_session.commit()

    # Create a session that expires soon
    token = create_session(db_session, user.id)
    session = get_session(db_session, token)
    assert session is not None

    # Manually set expires_at to past
    session.expires_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    db_session.add(session)
    db_session.commit()

    # Now it should be expired
    result = get_session(db_session, token)
    assert result is None


def test_middleware_uses_get_session(tmp_path):
    """Integration test to verify middleware uses get_session and respects expiration."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User
    from adapt.auth.password import hash_password
    from datetime import datetime, timezone, timedelta

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    
    # Create superuser
    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="admin", password_hash=hash_password("admin"), is_superuser=True, is_active=True)
        db.add(user)
        db.commit()
        
        # Create an expired session manually
        from adapt.auth.session import create_session
        token = create_session(db, user.id)
        session = db.exec(select(DBSession).where(DBSession.token == token)).first()
        # Make it expired
        session.expires_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
        db.add(session)
        db.commit()

    app = create_app(config)
    client = TestClient(app)
    
    # Set the expired cookie
    client.cookies.set("adapt_session", token)
    
    # Try to access protected API endpoint - should return 401 (not redirect)
    response = client.get("/admin/users", follow_redirects=False)
    assert response.status_code == 401  # API returns 401 for unauthenticated requests


def test_create_api_key_self(tmp_path):
    """Test that a non-superuser can create an API key for themselves."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User
    from adapt.auth.password import hash_password

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    
    # Create a regular user
    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()
        user_id = user.id

    app = create_app(config)
    client = TestClient(app)
    
    # Login as the user
    response = client.post("/auth/login", data={"username": "user", "password": "pass"})
    assert response.status_code == 200
    
    # Create API key
    response = client.post("/api/apikeys", json={"description": "Test key", "expires_in_days": 30})
    assert response.status_code == 201
    data = response.json()
    assert "key" in data
    assert "id" in data
    assert data["description"] == "Test key"
    
    # Verify the key was created in DB
    with Session(engine) as db:
        api_key = db.exec(select(APIKey).where(APIKey.user_id == user_id)).first()
        assert api_key is not None
        assert api_key.description == "Test key"
        assert api_key.is_active == True
        assert api_key.expires_at is not None
        # Expires in about 30 days
        expected_expires = datetime.now() + timedelta(days=30)
        assert abs((api_key.expires_at - expected_expires).total_seconds()) < 3600 * 6  # Within 6 hours due to timezone issues


def test_create_api_key_self_no_expiration(tmp_path):
    """Test creating API key without expiration."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User
    from adapt.auth.password import hash_password

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    
    # Create a regular user
    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()

    app = create_app(config)
    client = TestClient(app)
    
    # Login
    client.post("/auth/login", data={"username": "user", "password": "pass"})
    
    # Create API key without expiration
    response = client.post("/api/apikeys", json={"description": "No expire"})
    assert response.status_code == 201
    data = response.json()
    assert data["expires_at"] is None


def test_create_api_key_self_max_expiration(tmp_path):
    """Test that expiration cannot exceed 1 year."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User
    from adapt.auth.password import hash_password

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    
    # Create a regular user
    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()

    app = create_app(config)
    client = TestClient(app)
    
    # Login
    client.post("/auth/login", data={"username": "user", "password": "pass"})
    
    # Try to create API key with >1 year expiration
    response = client.post("/api/apikeys", json={"description": "Too long", "expires_in_days": 400})
    assert response.status_code == 400
    assert "expiration" in response.json()["detail"].lower()


def test_list_api_keys_self(tmp_path):
    """Test listing own API keys."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User, APIKey
    from adapt.auth.password import hash_password
    from adapt.api_keys import generate_api_key

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    
    # Create a regular user
    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()
        user_id = user.id
        
        # Create an API key manually
        raw_key, key_hash = generate_api_key()
        api_key = APIKey(
            key_hash=key_hash,
            user_id=user_id,
            description="Existing key",
            created_at=datetime.now(tz=timezone.utc),
            expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
            is_active=True
        )
        db.add(api_key)
        db.commit()

    app = create_app(config)
    client = TestClient(app)
    
    # Login
    client.post("/auth/login", data={"username": "user", "password": "pass"})
    
    # List API keys
    response = client.get("/api/apikeys")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["description"] == "Existing key"
    assert data[0]["is_active"] == True


def test_revoke_api_key_self(tmp_path):
    """Test revoking own API key."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User, APIKey
    from adapt.auth.password import hash_password
    from adapt.api_keys import generate_api_key

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    
    # Create a regular user
    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()
        user_id = user.id
        
        # Create an API key manually
        raw_key, key_hash = generate_api_key()
        api_key = APIKey(
            key_hash=key_hash,
            user_id=user_id,
            description="To revoke",
            created_at=datetime.now(tz=timezone.utc),
            is_active=True
        )
        db.add(api_key)
        db.commit()
        key_id = api_key.id

    app = create_app(config)
    client = TestClient(app)
    
    # Login
    client.post("/auth/login", data={"username": "user", "password": "pass"})
    
    # Revoke API key
    response = client.delete(f"/api/apikeys/{key_id}")
    assert response.status_code == 204
    
    # Verify revoked
    with Session(engine) as db:
        api_key = db.get(APIKey, key_id)
        assert api_key.is_active == False


def test_csrf_missing_cookie_rejected(tmp_path):
    """Cookie-authenticated write should be rejected when CSRF cookie is missing."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User
    from adapt.auth.password import hash_password

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)

    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()

    app = create_app(config)
    client = TestClient(app)

    login_response = client.post("/auth/login", data={"username": "user", "password": "pass"})
    assert login_response.status_code == 200

    client.cookies.pop("adapt_csrf", None)

    response = client.post("/api/apikeys", json={"description": "Should fail"})
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


def test_csrf_invalid_token_rejected(tmp_path):
    """Cookie-authenticated write should be rejected for invalid CSRF token."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User
    from adapt.auth.password import hash_password

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)

    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()

    app = create_app(config)
    client = TestClient(app)

    login_response = client.post("/auth/login", data={"username": "user", "password": "pass"})
    assert login_response.status_code == 200

    response = client.post(
        "/api/apikeys",
        json={"description": "Should fail"},
        headers={"X-CSRF-Token": "invalid-token"},
    )
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


def test_csrf_enforced_when_session_and_api_key_present(tmp_path):
    """If both session cookie and API key header are present, CSRF must still be required."""
    from fastapi.testclient import TestClient
    from adapt.config import AdaptConfig
    from adapt.app import create_app
    from adapt.storage import init_database, User, APIKey
    from adapt.auth.password import hash_password
    from adapt.api_keys import generate_api_key
    from datetime import datetime, timezone

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)

    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="user", password_hash=hash_password("pass"), is_superuser=False, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        raw_key, key_hash = generate_api_key()
        api_key = APIKey(
            key_hash=key_hash,
            user_id=user.id,
            description="Mixed auth test",
            created_at=datetime.now(tz=timezone.utc),
            is_active=True,
        )
        db.add(api_key)
        db.commit()

    app = create_app(config)
    client = TestClient(app)

    login_response = client.post("/auth/login", data={"username": "user", "password": "pass"})
    assert login_response.status_code == 200

    client.cookies.pop("adapt_csrf", None)

    response = client.post(
        "/api/apikeys",
        json={"description": "Should fail due to missing CSRF"},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()