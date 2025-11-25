import pytest
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from adapt.storage import User, Permission, DBSession, APIKey, init_database
from datetime import datetime, timezone
from adapt.auth.session import create_session


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = init_database(db_path)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_user_username_unique_db_constraint(db_session):
    # Insert first user
    user1 = User(username="user1", password_hash="hash", is_active=True)
    db_session.add(user1)
    db_session.commit()

    # Attempt to insert second user with identical username should raise IntegrityError
    user2 = User(username="user1", password_hash="hash2", is_active=True)
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_permission_unique_db_constraint(db_session):
    perm1 = Permission(resource="data", action="read", description="r")
    db_session.add(perm1)
    db_session.commit()

    perm2 = Permission(resource="data", action="read", description="duplicate")
    db_session.add(perm2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_db_session_token_unique_db_constraint(db_session):
    # Create a user
    user = User(username="u2", password_hash="hash", is_active=True)
    db_session.add(user)
    db_session.commit()

    # Create a session with a specified token
    token = "dup_token"
    s1 = DBSession(user_id=user.id, token=token, created_at=datetime.now(tz=timezone.utc), expires_at=datetime.now(tz=timezone.utc))
    db_session.add(s1)
    db_session.commit()

    s2 = DBSession(user_id=user.id, token=token, created_at=datetime.now(tz=timezone.utc), expires_at=datetime.now(tz=timezone.utc))
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        db_session.commit()
