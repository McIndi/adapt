import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from adapt.config import AdaptConfig
from adapt.app import create_app
from adapt.storage import init_database
from adapt.locks import LockManager
from adapt.storage import User
from adapt.auth.password import hash_password
from adapt.auth.session import create_session, SESSION_COOKIE
from sqlmodel import Session



@pytest.fixture
def app(tmp_path):
    # Setup a temporary environment
    config = AdaptConfig(root=tmp_path)
    
    # Create a dummy CSV file
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25")

    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    app = create_app(config)
    if not hasattr(app.state, 'lock_manager'):
        app.state.lock_manager = LockManager(engine)

    return app

@pytest.fixture
def superuser_client(app):
    from adapt.storage import User
    from adapt.auth.password import hash_password
    from adapt.auth.session import create_session, SESSION_COOKIE
    from sqlmodel import Session
    
    # Create superuser
    with Session(app.state.db_engine) as db:
        admin = User(username="admin", password_hash=hash_password("admin"), is_superuser=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_session(db, admin.id)
        
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)
    return client

@pytest.fixture
def readonly_app(tmp_path):
    # Setup a temporary environment with readonly=True
    config = AdaptConfig(root=tmp_path, readonly=True)
    
    # Create a dummy CSV file
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25")

    config = AdaptConfig(root=tmp_path, readonly=True)
    engine = init_database(config.db_path)
    app = create_app(config)
    if not hasattr(app.state, 'lock_manager'):
        app.state.lock_manager = LockManager(engine)

    return app

@pytest.fixture
def readonly_superuser_client(readonly_app):
    from adapt.storage import User
    from adapt.auth.password import hash_password
    from adapt.auth.session import create_session, SESSION_COOKIE
    from sqlmodel import Session
    
    # Create superuser
    with Session(readonly_app.state.db_engine) as db:
        admin = User(username="admin", password_hash=hash_password("admin"), is_superuser=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_session(db, admin.id)
        
    client = TestClient(readonly_app)
    client.cookies.set(SESSION_COOKIE, token)
    return client

def test_api_read(superuser_client):
    response = superuser_client.get("/api/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Alice"
    assert data[1]["name"] == "Bob"

def test_api_schema(superuser_client):
    response = superuser_client.get("/schema/data")
    assert response.status_code == 200
    schema = response.json()
    assert schema["name"] == "data"
    assert schema["columns"]["name"]["type"] == "string"
    assert schema["columns"]["age"]["type"] == "integer"

def test_ui_load(superuser_client):
    response = superuser_client.get("/ui/data")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Alice" not in response.text 
    assert "name" in response.text 

def test_api_create(superuser_client):
    new_row = {"name": "Charlie", "age": 35}
    response = superuser_client.post("/api/data", json={"action": "create", "data": [new_row]})
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify write
    response = superuser_client.get("/api/data")
    data = response.json()
    assert len(data) == 3
    assert data[2]["name"] == "Charlie"

def test_api_update(superuser_client):
    update_data = {"_row_id": 1, "age": 31}
    response = superuser_client.patch("/api/data", json={"action": "update", "data": update_data})
    assert response.status_code == 200
    
    response = superuser_client.get("/api/data")
    data = response.json()
    assert data[0]["age"] == 31

def test_api_delete(superuser_client):
    delete_data = {"_row_id": 2} # Bob
    response = superuser_client.request("DELETE", "/api/data", json={"action": "delete", "data": delete_data})
    assert response.status_code == 200
    
    response = superuser_client.get("/api/data")
    data = response.json()
    assert len(data) == 1 # Alice


def test_root_landing_page_html(superuser_client):
    """Test that root route returns HTML landing page for browsers."""
    response = superuser_client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "Welcome to Adapt" in response.text
    assert "Your Accessible Resources" in response.text


def test_root_api_json(superuser_client):
    """Test that root route returns JSON for API clients."""
    response = superuser_client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert "resources" in data
    assert isinstance(data["resources"], list)


def test_build_accessible_ui_links(app):
    """Test filtering of accessible UI links based on user permissions."""
    from adapt.utils import build_accessible_ui_links
    from adapt.storage import User, Permission, Group, UserGroup, GroupPermission
    from sqlmodel import Session
    
    # Create a mock request
    class MockRequest:
        def __init__(self, app, resources):
            self.app = app
            self.app.state.resources = resources
    
    # Mock resources
    class MockResource:
        def __init__(self, path, rtype, sub=None):
            self.relative_path = Path(path)
            self.resource_type = rtype
            self.metadata = {"sub_namespace": sub} if sub else {}
    
    resources = [
        MockResource("data.csv", "csv"),
        MockResource("doc.md", "markdown"),
        MockResource("book.xlsx", "excel", "Sheet1"),
    ]
    
    request = MockRequest(app, resources)
    
    # Test with no user (unauthenticated)
    links = build_accessible_ui_links(request, None)
    assert len(links) == 1
    assert links[0]["name"] == "doc"
    assert links[0]["url"] == "/doc"
    assert links[0]["type"] == "markdown"
    
    # Test with user having permission
    with Session(app.state.db_engine) as db:
        user = User(username="testuser", password_hash="dummy")
        db.add(user)
        db.commit()
        
        perm = Permission(resource="data", action="read")
        db.add(perm)
        db.commit()
        
        group = Group(name="testgroup")
        db.add(group)
        db.commit()
        
        ug = UserGroup(user_id=user.id, group_id=group.id)
        db.add(ug)
        gp = GroupPermission(group_id=group.id, permission_id=perm.id)
        db.add(gp)
        db.commit()

        from adapt.permissions import PermissionChecker
        checker = PermissionChecker(db)
        assert checker.has_permission(user, "data", "read") == True

        links = build_accessible_ui_links(request, user)
        assert len(links) == 2  # markdown + permitted csv
        names = [l["name"] for l in links]
        assert "doc" in names
        assert "data" in names


def test_readonly_mode_read_operations(readonly_superuser_client):
    """Test that read operations work in readonly mode."""
    response = readonly_superuser_client.get("/api/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Alice"
    assert data[1]["name"] == "Bob"


def test_readonly_mode_create_blocked(readonly_superuser_client):
    """Test that create operations are blocked in readonly mode."""
    new_row = {"name": "Charlie", "age": 35}
    response = readonly_superuser_client.post("/api/data", json={"action": "create", "data": [new_row]})
    assert response.status_code == 405
    assert "read-only mode" in response.json()["detail"].lower()


def test_readonly_mode_update_blocked(readonly_superuser_client):
    """Test that update operations are blocked in readonly mode."""
    update_data = {"_row_id": 1, "age": 31}
    response = readonly_superuser_client.patch("/api/data", json={"action": "update", "data": update_data})
    assert response.status_code == 405
    assert "read-only mode" in response.json()["detail"].lower()


def test_readonly_mode_delete_blocked(readonly_superuser_client):
    """Test that delete operations are blocked in readonly mode."""
    delete_data = {"_row_id": 2}
    response = readonly_superuser_client.request("DELETE", "/api/data", json={"action": "delete", "data": delete_data})
    assert response.status_code == 405
    assert "read-only mode" in response.json()["detail"].lower()


def test_readonly_mode_ui_hides_buttons(readonly_superuser_client):
    """Test that UI hides create/edit/delete buttons in readonly mode."""
    response = readonly_superuser_client.get("/ui/data")
    assert response.status_code == 200
    html = response.text
    # Should not contain the "Add New Record" button
    assert "Add New Record" not in html
    # Should not contain the Actions column header
    assert "<th>Actions</th>" not in html
    # Should not contain edit/delete buttons
    assert "btn-warning" not in html  # Edit button class
    assert "btn-danger" not in html   # Delete button class


