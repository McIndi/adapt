import pytest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from adapt.auth.session import get_session, create_session, SESSION_TTL
from adapt.storage import User, DBSession, init_database
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
    from adapt.cli import serve_app
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

    app = serve_app(config)
    client = TestClient(app)
    
    # Set the expired cookie
    client.cookies.set("adapt_session", token)
    
    # Try to access protected API endpoint - should return 401 (not redirect)
    response = client.get("/admin/users", follow_redirects=False)
    assert response.status_code == 401  # API returns 401 for unauthenticated requests