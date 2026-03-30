"""Tests for adapt.auth.dependencies: get_current_user, require_auth,
require_superuser, check_permission, and permission_dependency."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from sqlmodel import Session

from adapt.storage import (
    User, Group, Permission, UserGroup, GroupPermission, init_database
)
from adapt.auth.dependencies import (
    get_current_user, require_auth, require_superuser, check_permission,
    permission_dependency,
)
from adapt.auth.session import create_session
from adapt.api_keys import generate_api_key, create_api_key_record
from adapt.storage import APIKey
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine(tmp_path):
    eng = init_database(tmp_path / "test.db")
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def regular_user(db):
    user = User(username="regular", password_hash="x", is_active=True, is_superuser=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def superuser(db):
    user = User(username="super", password_hash="x", is_active=True, is_superuser=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_request(engine, cookies=None, headers=None):
    """Build a minimal mock Request with app.state.db_engine."""
    request = MagicMock()
    request.app.state.db_engine = engine
    request.cookies = cookies or {}
    request.headers = headers or {}
    return request


# ---------------------------------------------------------------------------
# get_current_user — unauthenticated
# ---------------------------------------------------------------------------

def test_get_current_user_no_credentials(engine):
    request = _make_request(engine)
    assert get_current_user(request) is None


# ---------------------------------------------------------------------------
# get_current_user — session cookie path
# ---------------------------------------------------------------------------

def test_get_current_user_valid_session(engine, db, regular_user):
    token = create_session(db, regular_user.id)
    request = _make_request(engine, cookies={"adapt_session": token})
    user = get_current_user(request)
    assert user is not None
    assert user.id == regular_user.id


def test_get_current_user_invalid_session(engine):
    request = _make_request(engine, cookies={"adapt_session": "bogus-token"})
    assert get_current_user(request) is None


# ---------------------------------------------------------------------------
# get_current_user — API key path
# ---------------------------------------------------------------------------

def test_get_current_user_valid_api_key(engine, db, regular_user):
    raw_key, api_key = create_api_key_record(db, regular_user.id, "test", None)
    request = _make_request(engine, headers={"X-API-Key": raw_key})
    user = get_current_user(request)
    assert user is not None
    assert user.id == regular_user.id


def test_get_current_user_invalid_api_key(engine):
    request = _make_request(engine, headers={"X-API-Key": "ak_notavalidkey"})
    assert get_current_user(request) is None


def test_get_current_user_revoked_api_key(engine, db, regular_user):
    raw_key, api_key = create_api_key_record(db, regular_user.id, "test", None)
    api_key.is_active = False
    db.add(api_key)
    db.commit()
    request = _make_request(engine, headers={"X-API-Key": raw_key})
    assert get_current_user(request) is None


# ---------------------------------------------------------------------------
# require_auth
# ---------------------------------------------------------------------------

def test_require_auth_authenticated(engine, db, regular_user):
    token = create_session(db, regular_user.id)
    request = _make_request(engine, cookies={"adapt_session": token})
    user = require_auth(request)
    assert user.id == regular_user.id


def test_require_auth_unauthenticated_raises(engine):
    request = _make_request(engine)
    with pytest.raises(HTTPException) as exc:
        require_auth(request)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# require_superuser
# ---------------------------------------------------------------------------

def test_require_superuser_grants_access(superuser):
    result = require_superuser(user=superuser)
    assert result.is_superuser is True


def test_require_superuser_blocks_regular_user(regular_user):
    with pytest.raises(HTTPException) as exc:
        require_superuser(user=regular_user)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# check_permission
# ---------------------------------------------------------------------------

def test_check_permission_superuser_always_true(db, superuser):
    # Superuser should pass even with no permissions in DB
    assert check_permission(superuser, db, "write", "some_resource") is True


def test_check_permission_no_groups(db, regular_user):
    assert check_permission(regular_user, db, "read", "any_resource") is False


def test_check_permission_with_matching_permission(db, regular_user):
    group = Group(name="readers")
    db.add(group)
    db.commit()
    db.refresh(group)

    perm = Permission(action="read", resource="reports")
    db.add(perm)
    db.commit()
    db.refresh(perm)

    db.add(UserGroup(user_id=regular_user.id, group_id=group.id))
    db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
    db.commit()

    assert check_permission(regular_user, db, "read", "reports") is True


def test_check_permission_wrong_action(db, regular_user):
    group = Group(name="readers2")
    db.add(group)
    db.commit()
    db.refresh(group)

    perm = Permission(action="read", resource="reports")
    db.add(perm)
    db.commit()
    db.refresh(perm)

    db.add(UserGroup(user_id=regular_user.id, group_id=group.id))
    db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
    db.commit()

    assert check_permission(regular_user, db, "write", "reports") is False


def test_check_permission_wrong_resource(db, regular_user):
    group = Group(name="writers")
    db.add(group)
    db.commit()
    db.refresh(group)

    perm = Permission(action="write", resource="invoices")
    db.add(perm)
    db.commit()
    db.refresh(perm)

    db.add(UserGroup(user_id=regular_user.id, group_id=group.id))
    db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
    db.commit()

    assert check_permission(regular_user, db, "write", "reports") is False
