import pytest
from fastapi.testclient import TestClient
from adapt.config import AdaptConfig
from adapt.app import create_app
from adapt.storage import init_database, User
from adapt.auth.password import hash_password
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
    
    # 4. Create user
    new_user = {"username": "testuser", "password": "password", "is_superuser": False}
    response = client.post("/admin/users", json=new_user)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["is_superuser"] is False
    
    # 5. Delete user
    user_id = data["id"]
    response = client.delete(f"/admin/users/{user_id}")
    assert response.status_code == 200
    
    # Verify gone
    response = client.get("/admin/users")
    users = response.json()
    assert not any(u["id"] == user_id for u in users)

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
