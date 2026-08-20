import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from adapt.config import AdaptConfig
from adapt.app import create_app
from adapt.storage import APIKey, DBSession, init_database, User
from adapt.auth.password import hash_password, verify_password
from adapt.auth.session import create_session
from pathlib import Path
import io
import sys
from contextlib import redirect_stdout

@pytest.fixture
def app(tmp_path):
    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    
    # Create superuser
    from sqlmodel import Session
    with Session(engine) as db:
        user = User(username="admin", password_hash=hash_password("admin"), is_superuser=True, is_active=True)
        db.add(user)
        db.commit()
        
    return create_app(config)

@pytest.fixture
def client(app):
    return TestClient(app)

def test_login_page(client):
    # Check that login page exists
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "Sign In" in response.text

def test_admin_ui_redirect(client):
    # Should redirect to login
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["location"]

def test_admin_ui_renders_for_superuser(client):
    """The admin UI must actually render once logged in.

    Regression: ui.py called TemplateResponse(name, context) — the removed
    Starlette signature — which passed the context dict where the template name
    belongs and raised a TypeError. Only the unauthenticated redirect was
    covered, and TestClient follows that redirect to the login page, so the
    render path was never exercised.
    """
    response = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200

    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<h1>Adapt</h1>" in response.text
    assert 'data-sortable-table' in response.text
    assert "Reset Password" in response.text
    assert "File Uploads" in response.text
    assert 'id="upload-form"' in response.text


def test_profile_page_includes_sortable_table_support(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200

    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/static/sortable-tables.js" in response.text
    assert "data-sortable-table" in response.text
    assert 'id="change-password-form"' in response.text


def test_admin_flow(client):
    # 1. Access denied (API)
    response = client.get("/admin/users")
    assert response.status_code == 401
    
    # 2. Login
    response = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    
    # 3. List users
    response = client.get("/admin/users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1
    assert users[0]["username"] == "admin"
    assert "password_hash" not in users[0]
    
    # 4. Create user
    new_user = {"username": "testuser", "password": "password", "is_superuser": False}
    response = client.post("/admin/users", json=new_user)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["is_superuser"] is False
    assert "password_hash" not in data
    
    # 5. Delete user
    user_id = data["id"]
    response = client.delete(f"/admin/users/{user_id}")
    assert response.status_code == 200
    
    # Verify gone
    response = client.get("/admin/users")
    users = response.json()
    assert not any(u["id"] == user_id for u in users)


def test_admin_can_reset_password_and_revoke_user_sessions(client, app):
    client.post("/auth/login", data={"username": "admin", "password": "admin"})
    created = client.post(
        "/admin/users",
        json={"username": "reset_user", "password": "old-password"},
    ).json()

    with Session(app.state.db_engine) as db:
        old_token = create_session(db, created["id"])

    response = client.put(
        f"/admin/users/{created['id']}/password",
        json={"new_password": "New!Secure-Phrase3"},
    )
    assert response.status_code == 200
    assert response.json()["sessions_revoked"] is True

    with Session(app.state.db_engine) as db:
        user = db.get(User, created["id"])
        assert verify_password("New!Secure-Phrase3", user.password_hash)
        assert db.exec(select(DBSession).where(DBSession.token == old_token)).first() is None


def test_deactivated_user_cannot_authenticate_and_can_be_reactivated(client, app):
    """Deactivation must block login, sessions, and API keys immediately."""
    client.post("/auth/login", data={"username": "admin", "password": "admin"})
    created = client.post(
        "/admin/users",
        json={"username": "inactive_user", "password": "account-password"},
    ).json()

    user_client = TestClient(app)
    assert user_client.post(
        "/auth/login",
        data={"username": "inactive_user", "password": "account-password"},
    ).status_code == 200
    key_response = user_client.post(
        "/api/apikeys",
        json={"description": "Retained while inactive"},
    )
    assert key_response.status_code == 201
    raw_key = key_response.json()["key"]

    response = client.put(
        f"/admin/users/{created['id']}/status",
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "is_active": False,
        "sessions_revoked": 1,
    }

    assert user_client.get("/auth/me").status_code == 401
    assert TestClient(app).get(
        "/auth/me", headers={"X-API-Key": raw_key}
    ).status_code == 401
    assert user_client.post(
        "/auth/login",
        data={"username": "inactive_user", "password": "account-password"},
    ).status_code == 401

    with Session(app.state.db_engine) as db:
        target = db.get(User, created["id"])
        assert target.is_active is False
        assert db.exec(
            select(DBSession).where(DBSession.user_id == target.id)
        ).all() == []
        key = db.exec(select(APIKey).where(APIKey.user_id == target.id)).one()
        assert key.is_active is True
        assert key.last_used_at is None

    response = client.put(
        f"/admin/users/{created['id']}/status",
        json={"is_active": True},
    )
    assert response.status_code == 200
    assert TestClient(app).get(
        "/auth/me", headers={"X-API-Key": raw_key}
    ).status_code == 200


def test_admin_cannot_deactivate_current_user(client):
    client.post("/auth/login", data={"username": "admin", "password": "admin"})
    admin = client.get("/admin/users").json()[0]

    response = client.put(
        f"/admin/users/{admin['id']}/status",
        json={"is_active": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot deactivate yourself"

def test_group_flow(client):
    # Login
    client.post("/auth/login", data={"username": "admin", "password": "admin"})
    
    # Create User
    user_res = client.post("/admin/users", json={"username": "member", "password": "pw"})
    user_id = user_res.json()["id"]

    # Create Group
    group_data = {"name": "Editors", "description": "Can edit files"}
    response = client.post("/admin/groups", json=group_data)
    assert response.status_code == 200
    group = response.json()
    group_id = group["id"]
    
    # Add Member
    response = client.post(f"/admin/groups/{group_id}/users/{user_id}")
    assert response.status_code == 200
    
    # Verify Member in Group
    response = client.get(f"/admin/groups/{group_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["users"]) == 1
    assert data["users"][0]["username"] == "member"
    assert "password_hash" not in data["users"][0]
    
    # Remove Member
    response = client.delete(f"/admin/groups/{group_id}/users/{user_id}")
    assert response.status_code == 200
    
    # Verify Removed
    response = client.get(f"/admin/groups/{group_id}")
    data = response.json()
    assert len(data["users"]) == 0
    
    # Delete Group
    response = client.delete(f"/admin/groups/{group_id}")
    assert response.status_code == 200


def test_login_next_open_redirect_blocked(client):
    """Unsafe absolute next URLs should be blocked and replaced by root path."""
    response = client.get("/auth/login?next=https://evil.example", follow_redirects=False)
    assert response.status_code == 200
    assert "sanitizeNextPath" in response.text


def test_unauth_redirect_uses_safe_next(client):
    """Unauthenticated HTML redirects should keep a relative next path only."""
    response = client.get("/admin/users", headers={"Accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("/auth/login?next=")
    assert "http" not in location

def test_permission_flow(client):
    # Login
    client.post("/auth/login", data={"username": "admin", "password": "admin"})
    
    # Create Permission
    perm_data = {"resource": "documents", "action": "read", "description": "Read docs"}
    response = client.post("/admin/permissions", json=perm_data)
    assert response.status_code == 200
    perm = response.json()
    perm_id = perm["id"]
    
    # List Permissions
    response = client.get("/admin/permissions")
    assert response.status_code == 200
    perms = response.json()
    assert any(p["id"] == perm_id for p in perms)
    
    # Create Group
    group_res = client.post("/admin/groups", json={"name": "Readers"})
    group_id = group_res.json()["id"]
    
    # Assign Permission to Group
    response = client.post(f"/admin/groups/{group_id}/permissions/{perm_id}")
    assert response.status_code == 200
    
    # Verify Group Permissions
    response = client.get(f"/admin/groups/{group_id}/permissions")
    assert response.status_code == 200
    group_perms = response.json()
    assert len(group_perms) == 1
    assert group_perms[0]["id"] == perm_id
    
    # Remove Permission
    response = client.delete(f"/admin/groups/{group_id}/permissions/{perm_id}")
    assert response.status_code == 200
    
    # Verify Removed
    response = client.get(f"/admin/groups/{group_id}/permissions")
    assert len(response.json()) == 0
    
    # Delete Permission
    response = client.delete(f"/admin/permissions/{perm_id}")
    assert response.status_code == 200


def test_permission_root_boundary_normalization(client):
    client.post("/auth/login", data={"username": "admin", "password": "admin"})

    root_write = client.post(
        "/admin/permissions",
        json={"resource": "__root__", "action": "write", "description": "Root write"},
    )
    assert root_write.status_code == 200
    root_write_payload = root_write.json()
    assert root_write_payload["resource"] == ""
    assert root_write_payload["action"] == "write"

    root_read = client.post(
        "/admin/permissions",
        json={"resource": "", "action": "read", "description": "Root read"},
    )
    assert root_read.status_code == 200
    root_read_payload = root_read.json()
    assert root_read_payload["resource"] == ""
    assert root_read_payload["action"] == "read"

    perms = client.get("/admin/permissions")
    assert perms.status_code == 200
    rows = perms.json()
    assert any(p["id"] == root_write_payload["id"] and p["resource"] == "" for p in rows)
    assert any(p["id"] == root_read_payload["id"] and p["resource"] == "" for p in rows)


def test_admin_api_key_validation_and_soft_revoke(client, db_session):
    """Admin API key create should validate expiration; revoke should deactivate, not delete."""
    from adapt.storage import APIKey

    # Login
    client.post("/auth/login", data={"username": "admin", "password": "admin"})

    # Create key with too-large expiration should fail
    response = client.post("/admin/api-keys", json={
        "user_id": 1,
        "description": "test key",
        "expires_in_days": 366,
    })
    assert response.status_code == 400

    # Valid key creation
    response = client.post("/admin/api-keys", json={
        "user_id": 1,
        "description": "test key",
        "expires_in_days": 30,
    })
    assert response.status_code == 200
    data = response.json()
    assert "created_at" in data
    key_id = data["id"]

    # Revoke should deactivate instead of delete
    response = client.delete(f"/admin/api-keys/{key_id}")
    assert response.status_code == 200
    record = db_session.get(APIKey, key_id)
    assert record is not None
    assert record.is_active is False


# CLI Command Tests

@pytest.fixture
def db_session(tmp_path):
    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    from sqlmodel import Session
    with Session(engine) as session:
        yield session


def test_run_list_groups_empty(db_session, tmp_path, capsys):
    """Test list-groups command with no groups."""
    from adapt.commands.admin import run_list_groups
    
    run_list_groups(tmp_path)
    
    captured = capsys.readouterr()
    assert "No groups found." in captured.out


def test_run_list_groups_with_data(db_session, tmp_path, capsys):
    """Test list-groups command with groups, permissions, and users."""
    from adapt.commands.admin import run_list_groups
    from adapt.storage import Group, Permission, GroupPermission, User, UserGroup, Action
    from sqlmodel import select
    
    # Create test data
    # Users
    user1 = User(username="alice", password_hash="dummy", is_active=True)
    user2 = User(username="bob", password_hash="dummy", is_active=True)
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    
    # Groups
    group1 = Group(name="admins", description="Admin group")
    group2 = Group(name="users", description="Regular users")
    db_session.add(group1)
    db_session.add(group2)
    db_session.commit()
    db_session.refresh(group1)
    db_session.refresh(group2)
    
    # Permissions
    perm1 = Permission(resource="data.csv", action=Action.read, description="Read data")
    perm2 = Permission(resource="data.csv", action=Action.write, description="Write data")
    perm3 = Permission(resource="config.txt", action=Action.read, description="Read config")
    db_session.add(perm1)
    db_session.add(perm2)
    db_session.add(perm3)
    db_session.commit()
    db_session.refresh(perm1)
    db_session.refresh(perm2)
    db_session.refresh(perm3)
    
    # Group Permissions
    gp1 = GroupPermission(group_id=group1.id, permission_id=perm1.id)
    gp2 = GroupPermission(group_id=group1.id, permission_id=perm2.id)
    gp3 = GroupPermission(group_id=group2.id, permission_id=perm1.id)
    gp4 = GroupPermission(group_id=group2.id, permission_id=perm3.id)
    db_session.add(gp1)
    db_session.add(gp2)
    db_session.add(gp3)
    db_session.add(gp4)
    
    # User Groups
    ug1 = UserGroup(user_id=user1.id, group_id=group1.id)
    ug2 = UserGroup(user_id=user2.id, group_id=group1.id)
    ug3 = UserGroup(user_id=user2.id, group_id=group2.id)
    db_session.add(ug1)
    db_session.add(ug2)
    db_session.add(ug3)
    
    db_session.commit()
    
    run_list_groups(tmp_path)
    
    captured = capsys.readouterr()
    output = captured.out
    
    # Check that groups are listed
    assert "Group: admins" in output
    assert "Description: Admin group" in output
    assert "Group: users" in output
    assert "Description: Regular users" in output
    
    # Check permissions
    assert "read on data.csv" in output
    assert "write on data.csv" in output
    assert "read on config.txt" in output
    
    # Check users
    assert "- alice" in output
    assert "- bob" in output


def test_run_list_resources(tmp_path, capsys):
    """Test list-resources command."""
    from adapt.commands.admin import run_list_resources
    
    # Create some test files with supported extensions
    (tmp_path / "data.csv").write_text("a,b\n1,2")
    (tmp_path / "readme.md").write_text("# Hello")
    
    run_list_resources(tmp_path)
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "Discovered resources:" in output
    assert "data" in output  # extension stripped
    assert "readme" in output  # extension stripped


def test_run_create_permissions(tmp_path, capsys):
    """Test create-permissions command."""
    from adapt.commands.admin import run_create_permissions
    from adapt.storage import Group, Permission, GroupPermission
    from sqlmodel import Session, select
    
    # Create some test files
    (tmp_path / "data.csv").write_text("a,b\n1,2")
    (tmp_path / "test.txt").write_text("hello")
    
    # Mock args
    class Args:
        resources = ["data.csv", "test.txt"]
        all_group = "all_resources"
        read_group = "read_resources"
        root = str(tmp_path)
    
    args = Args()
    
    run_create_permissions(
        root=tmp_path,
        resources=args.resources,
        all_group_name=args.all_group,
        read_group_name=args.read_group
    )
    
    captured = capsys.readouterr()
    output = captured.out
    
    # Check output
    assert "Created permission read on data.csv" in output
    assert "Created permission write on data.csv" in output
    assert "Created permission read on test.txt" in output
    assert "Created permission write on test.txt" in output
    assert "Created group 'all_resources_data.csv_test.txt'" in output
    assert "Created group 'read_resources_data.csv_test.txt'" in output
    
    # Verify in database
    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    with Session(engine) as db:
        groups = db.exec(select(Group)).all()
        assert len(groups) == 6  # all, read, and 4 individual groups (2 per resource * 2 actions? wait no)
        # Actually, the function creates all, read, and for each resource: readonly and readwrite groups
        # So for 2 resources: all, read, and 4 individual = 6 total
        
        permissions = db.exec(select(Permission)).all()
        assert len(permissions) == 4  # 2 resources * 2 actions


def test_run_user_and_group_admin_commands(tmp_path, capsys):
    """Test user/group CRUD and membership admin CLI commands."""
    from adapt.commands.admin import (
        run_create_user,
        run_list_users,
        run_delete_user,
        run_create_group,
        run_delete_group,
        run_add_to_group,
        run_remove_from_group,
    )

    run_create_user(
        tmp_path,
        username="alice",
        password="pw",
        password_confirm="pw",
        is_superuser=False,
        allow_weak_password=True,
    )
    run_create_group(tmp_path, name="editors", description="Editors group")
    run_add_to_group(tmp_path, username="alice", group_name="editors")

    run_list_users(tmp_path)
    output = capsys.readouterr().out
    assert "Added user 'alice' to group 'editors'" in output
    assert "alice (active)" in output

    run_remove_from_group(tmp_path, username="alice", group_name="editors")
    run_delete_group(tmp_path, name="editors")
    run_delete_user(tmp_path, username="alice")

    output = capsys.readouterr().out
    assert "Removed user 'alice' from group 'editors'" in output
    assert "Deleted group 'editors'" in output
    assert "Deleted user 'alice'" in output


def test_run_create_user_retries_until_passwords_match(tmp_path, capsys, monkeypatch):
    from sqlmodel import Session, select

    from adapt.commands import passwords as password_helpers
    from adapt.commands.admin import run_create_user

    entries = iter([
        "StrongPass#2026",
        "not-the-same",
        "StrongPass#2026",
        "StrongPass#2026",
    ])
    monkeypatch.setattr(password_helpers.getpass, "getpass", lambda _: next(entries))

    run_create_user(tmp_path, username="alice", password=None, is_superuser=False)

    output = capsys.readouterr().out
    assert "Passwords do not match. Please try again." in output
    assert "Created user 'alice'" in output

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == "alice")).first()
        assert user is not None


def test_run_create_user_accepts_weak_password_after_confirmation(tmp_path, capsys, monkeypatch):
    from sqlmodel import Session, select

    from adapt.commands import passwords as password_helpers
    from adapt.commands.admin import run_create_user

    entries = iter(["password", "password"])
    prompts = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "y"

    monkeypatch.setattr(password_helpers.getpass, "getpass", lambda _: next(entries))
    monkeypatch.setattr("builtins.input", fake_input)

    run_create_user(tmp_path, username="bob", password=None, is_superuser=False)

    output = capsys.readouterr().out
    assert "Created user 'bob'" in output
    assert prompts == ["This password appears weak and may be easily guessed. Use it anyway? [y/N]: "]

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == "bob")).first()
        assert user is not None


def test_run_create_user_rejects_weak_password_without_override_noninteractive(tmp_path, capsys, monkeypatch):
    from sqlmodel import Session, select

    from adapt.commands import passwords as password_helpers
    from adapt.commands.admin import run_create_user

    class FakeStdin:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(password_helpers.sys, "stdin", FakeStdin())

    run_create_user(
        tmp_path,
        username="carol",
        password="password",
        password_confirm="password",
        is_superuser=False,
    )

    output = capsys.readouterr().out
    assert "Choose a stronger password or re-run with --allow-weak-password." in output

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == "carol")).first()
        assert user is None


def test_run_add_superuser_accepts_override_for_weak_password_noninteractive(tmp_path, capsys, monkeypatch):
    from sqlmodel import Session, select

    from adapt.commands import passwords as password_helpers
    from adapt.commands.addsuperuser import run_add_superuser

    class FakeStdin:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(password_helpers.sys, "stdin", FakeStdin())

    assert run_add_superuser(
        tmp_path,
        username="root2",
        password="password",
        password_confirm="password",
        allow_weak_password=True,
    ) is True

    output = capsys.readouterr().out
    assert "Created superuser 'root2'" in output

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == "root2")).first()
        assert user is not None
        assert user.is_superuser is True

    assert run_add_superuser(
        tmp_path,
        username="root2",
        password="password",
        password_confirm="password",
        allow_weak_password=True,
    ) is True
    assert "User 'root2' already exists" in capsys.readouterr().out


def test_cache_admin(client):
    # Login first
    response = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    
    # Test list cache
    response = client.get("/admin/cache")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Check structure
    if data:
        entry = data[0]
        assert 'key' in entry
        assert 'expires_at' in entry
        assert 'resource' in entry
        assert 'user' in entry
    
    # Test clear cache
    response = client.delete("/admin/cache")
    assert response.status_code == 200
    assert response.json() == {"success": True}

    # Test delete single cache entry (if any exist)
    response = client.get("/admin/cache")
    data = response.json()
    if data:
        entry = data[0]
        key = entry['key']
        resource = entry['resource']
        response = client.delete(f"/admin/cache/{key}?resource={resource}")
        assert response.status_code == 200
        assert response.json() == {"success": True}

def test_audit_logs_filtering(client):
    # Login first
    response = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    
    # Test list audit logs without filters
    response = client.get("/admin/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # Test with user_id filter (should work even if no matches)
    response = client.get("/admin/audit-logs?user_id=999")
    assert response.status_code == 200
    filtered_data = response.json()
    assert isinstance(filtered_data, list)
    
    # Test with action filter
    response = client.get("/admin/audit-logs?action=login")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_health_unauthenticated(client):
    """Test /health endpoint for unauthenticated users."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    # Should not include authenticated-only fields
    assert "uptime_seconds" not in data
    assert "cache_size" not in data
    assert "endpoint_count" not in data


def test_health_authenticated(client):
    """Test /health endpoint for authenticated users."""
    # Login first
    response = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200

    # Now test health endpoint
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    # Should include authenticated-only fields
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int)
    assert "cache_size" in data
    assert isinstance(data["cache_size"], int) or data["cache_size"] is None
    assert "endpoint_count" in data
    assert isinstance(data["endpoint_count"], int)


def test_media_gallery_redirects_when_unauthenticated(client):
    """Unauthenticated users should be redirected to login for media UI."""
    response = client.get("/ui/media", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login?next=/ui/media"
