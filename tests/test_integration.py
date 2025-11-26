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
def client(app):
    return TestClient(app)

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


