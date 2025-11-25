import pytest
from sqlmodel import select
from adapt.storage import User, APIKey, DBSession, UserGroup, Group, AuditLog, init_database
from adapt.auth.password import hash_password


def test_api_key_cascade_on_user_delete(db_session):
    # Create user
    user = User(username="del_user_api", password_hash=hash_password("pass"), is_superuser=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create API key for user
    key = APIKey(user_id=user.id, key_hash="testhash", description="test")
    db_session.add(key)
    db_session.commit()
    db_session.refresh(key)

    key_id = key.id

    # Delete the user
    db_session.delete(user)
    db_session.commit()

    # API Key should be deleted due to ON DELETE CASCADE
    found = db_session.get(APIKey, key_id)
    assert found is None


def test_session_cascade_on_user_delete(db_session):
    user = User(username="del_user_session", password_hash=hash_password("pass"), is_superuser=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    s = DBSession(user_id=user.id, token="tok123")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    sid = s.id

    db_session.delete(user)
    db_session.commit()

    assert db_session.get(DBSession, sid) is None


def test_usergroup_cascade_on_group_delete(db_session):
    # Create user
    user = User(username="del_user_group", password_hash=hash_password("pass"), is_superuser=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create group
    group = Group(name="del_group")
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    # Add membership
    ug = UserGroup(user_id=user.id, group_id=group.id)
    db_session.add(ug)
    db_session.commit()

    # Delete group
    db_session.delete(group)
    db_session.commit()

    # UserGroup entry should be gone
    res = db_session.exec(select(UserGroup).where(UserGroup.user_id == user.id)).first()
    assert res is None


def test_auditlog_set_null_on_user_delete(db_session):
    user = User(username="auditlog_user", password_hash=hash_password("pass"), is_superuser=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    log = AuditLog(user_id=user.id, action="test_action", resource="user", details="test")
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    lid = log.id

    # Delete user
    db_session.delete(user)
    db_session.commit()

    # Audit log should persist and have user_id set to None
    l = db_session.get(AuditLog, lid)
    assert l is not None
    assert l.user_id is None
