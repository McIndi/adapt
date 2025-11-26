import pytest
from fastapi.testclient import TestClient
from adapt.config import AdaptConfig
from adapt.app import create_app
from adapt.storage import init_database, User
from adapt.auth.password import hash_password

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
