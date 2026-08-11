import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from adapt.config import AdaptConfig
from adapt.app import create_app
from adapt.storage import init_database
from adapt.api_keys import create_api_key_record
from adapt.locks import LockManager, LockTimeoutError
from adapt.storage import AuditLog, Group, GroupPermission, Permission, User, UserGroup
from adapt.auth.password import hash_password
from adapt.auth.session import create_session, SESSION_COOKIE
from adapt.security import CSRF_COOKIE_NAME, generate_csrf_token
from sqlmodel import Session, select



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
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())
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
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())
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


def test_text_file_serves_plain_text(tmp_path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\nBob,25")

    app = create_app(AdaptConfig(root=tmp_path))
    with Session(app.state.db_engine) as db:
        admin = User(username="admin_text", password_hash=hash_password("admin"), is_superuser=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_session(db, admin.id)

    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())

    response = client.get("/notes")
    assert response.status_code == 200
    assert response.text.splitlines() == ["alpha", "beta"]
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"].startswith("inline;")


def test_pdf_file_serves_inline_or_download(tmp_path):
    pdf_file = tmp_path / "paper.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%test\n")
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\nBob,25")

    app = create_app(AdaptConfig(root=tmp_path))
    with Session(app.state.db_engine) as db:
        admin = User(username="admin_pdf", password_hash=hash_password("admin"), is_superuser=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_session(db, admin.id)

    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())

    inline_response = client.get("/paper")
    assert inline_response.status_code == 200
    assert inline_response.headers["content-type"].startswith("application/pdf")
    assert inline_response.headers["content-disposition"].startswith("inline;")

    download_response = client.get("/paper?download=true")
    assert download_response.status_code == 200
    assert download_response.headers["content-disposition"].startswith("attachment;")


def test_ui_hides_write_controls_for_read_only_user(tmp_path):
    """UI should hide add/edit/delete controls when user has read but not write permission."""
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\nBob,25")

    app = create_app(AdaptConfig(root=tmp_path))
    client = TestClient(app)

    with Session(app.state.db_engine) as db:
        user = User(username="reader_ui", password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)

        permission = Permission(resource="data", action="read")
        db.add(permission)
        db.commit()
        db.refresh(permission)

        group = Group(name="ui_readers")
        db.add(group)
        db.commit()
        db.refresh(group)

        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.add(GroupPermission(group_id=group.id, permission_id=permission.id))
        db.commit()

        token = create_session(db, user.id)

    client.cookies.set(SESSION_COOKIE, token)

    response = client.get("/ui/data")
    assert response.status_code == 200
    assert "Add New Record" not in response.text
    assert "<th>Actions</th>" not in response.text
    assert "Edit</button>" not in response.text
    assert "Delete</button>" not in response.text

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


def test_api_exhausted_lock_conflict_returns_409(superuser_client, monkeypatch):
    class ExhaustedLock:
        def __enter__(self):
            raise LockTimeoutError("Failed to acquire lock on data.csv after 30s")

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(
        superuser_client.app.state.lock_manager,
        "lock",
        lambda *args, **kwargs: ExhaustedLock(),
    )

    response = superuser_client.post(
        "/api/data",
        json={"action": "create", "data": [{"name": "Charlie", "age": 35}]},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Failed to acquire lock on data.csv after 30s",
    }


@pytest.mark.parametrize(
    ("row", "detail"),
    [
        (
            {"name": "Charlie", "age": "not-an-integer"},
            "Schema validation failed: column 'age': expected integer, received string",
        ),
        (
            {"name": "Charlie", "age": 35, "ignored": "value"},
            "Schema validation failed: unknown column 'ignored'",
        ),
    ],
)
def test_api_create_rejects_values_that_violate_schema(superuser_client, row, detail):
    response = superuser_client.post(
        "/api/data",
        json={"action": "create", "data": [row]},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    assert [row["name"] for row in superuser_client.get("/api/data").json()] == ["Alice", "Bob"]

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


@pytest.mark.parametrize(
    ("method", "action", "data", "audit_action", "details"),
    [
        (
            "POST",
            "create",
            [{"name": "Charlie", "age": 35}],
            "create_dataset_rows",
            "Created 1 dataset row",
        ),
        (
            "PATCH",
            "update",
            {"_row_id": 1, "age": 31},
            "update_dataset_row",
            "Updated dataset row 1",
        ),
        (
            "DELETE",
            "delete",
            {"_row_id": 2},
            "delete_dataset_row",
            "Deleted dataset row 2",
        ),
    ],
)
def test_dataset_mutations_create_audit_entries(
    app, method, action, data, audit_action, details
):
    with Session(app.state.db_engine) as db:
        user = User(
            username=f"{action}_auditor",
            password_hash=hash_password("password"),
            is_superuser=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
        raw_key, _ = create_api_key_record(db, user_id, "audit test", None)

    response = TestClient(app).request(
        method,
        "/api/data",
        headers={"X-API-Key": raw_key},
        json={"action": action, "data": data},
    )

    assert response.status_code == 200
    with Session(app.state.db_engine) as db:
        entries = db.exec(
            select(AuditLog).where(AuditLog.action == audit_action)
        ).all()

    assert len(entries) == 1
    assert entries[0].user_id == user_id
    assert entries[0].resource == "data.csv"
    assert entries[0].details == details


def test_root_landing_page_html(superuser_client):
    """Test that root route returns HTML landing page for browsers."""
    superuser_client.app.state.config.upload["enabled"] = True
    response = superuser_client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "Welcome to Adapt" in response.text
    assert "Your Accessible Resources" in response.text
    assert 'data-sortable-table' in response.text
    assert "Logout" in response.text
    assert "Upload Files" in response.text
    assert 'id="landing-upload-form"' in response.text
    assert "Sign in to access this Adapt workspace" not in response.text


def test_root_landing_page_html_anonymous(client):
    """Test that anonymous browser requests receive the sign-in landing page."""
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "Sign in to access this Adapt workspace" in response.text
    assert "contact your Adapt administrator" in response.text
    assert "Logout" not in response.text
    assert "Your Accessible Resources" not in response.text


def test_root_landing_page_html_shows_upload_form_for_root_writer(app):
    """Test that authenticated non-admin users with root write can see the upload surface."""
    app.state.config.upload["enabled"] = True

    with Session(app.state.db_engine) as db:
        user = User(username="uploader", password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)

        permission = Permission(resource="", action="write")
        db.add(permission)
        db.commit()
        db.refresh(permission)

        group = Group(name="uploaders")
        db.add(group)
        db.commit()
        db.refresh(group)

        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.add(GroupPermission(group_id=group.id, permission_id=permission.id))
        db.commit()

        token = create_session(db, user.id)

    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())

    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "Upload Files" in response.text
    assert 'id="landing-upload-form"' in response.text
    assert "Document root" in response.text or "document root" in response.text


def test_root_api_json(superuser_client):
    """Test that root route returns JSON for API clients."""
    response = superuser_client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert "resources" in data
    assert isinstance(data["resources"], list)


def test_root_api_json_anonymous_hides_resources(client):
    """Test that anonymous JSON discovery does not enumerate protected resources."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json() == {"resources": []}


def test_openapi_json_hides_resource_paths_for_anonymous(client):
    """Test that anonymous OpenAPI responses omit protected resource routes."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    assert "/auth/login" in paths
    assert all(not path.startswith("/api/data") for path in paths)
    assert all(not path.startswith("/schema/data") for path in paths)
    assert all(not path.startswith("/ui/data") for path in paths)


def test_openapi_json_only_shows_permitted_resource_paths(tmp_path):
    """Test that OpenAPI only includes resource routes the authenticated user may read."""
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\nBob,25")
    (tmp_path / "secret.csv").write_text("name,age\nMallory,99")

    app = create_app(AdaptConfig(root=tmp_path))
    client = TestClient(app)

    with Session(app.state.db_engine) as db:
        user = User(username="reader", password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)

        permission = Permission(resource="data", action="read")
        db.add(permission)
        db.commit()
        db.refresh(permission)

        group = Group(name="readers")
        db.add(group)
        db.commit()
        db.refresh(group)

        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.add(GroupPermission(group_id=group.id, permission_id=permission.id))
        db.commit()

        token = create_session(db, user.id)

    client.cookies.set(SESSION_COOKIE, token)

    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    assert any(path.startswith("/api/data") for path in paths)
    assert any(path.startswith("/schema/data") for path in paths)
    assert any(path.startswith("/ui/data") for path in paths)
    assert all(not path.startswith("/api/secret") for path in paths)
    assert all(not path.startswith("/schema/secret") for path in paths)
    assert all(not path.startswith("/ui/secret") for path in paths)
    assert all(not path.startswith("/admin") for path in paths)


def test_openapi_json_prunes_admin_only_components_for_non_superuser(tmp_path):
    """Filtering out admin paths must not leak their models in components.schemas.

    A non-superuser's document should carry no field-level shape for
    admin-only request/response models like UserPublic or Permission.
    """
    app = create_app(AdaptConfig(root=tmp_path))
    client = TestClient(app)

    with Session(app.state.db_engine) as db:
        user = User(username="nonadmin", password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)

    client.cookies.set(SESSION_COOKIE, token)

    schema = client.get("/openapi.json").json()
    admin_only_models = {"UserPublic", "UserCreate", "Permission", "PermissionCreate", "Group", "GroupCreate"}
    schema_names = set(schema.get("components", {}).get("schemas", {}))
    assert not (schema_names & admin_only_models)


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
        MockResource("notes.txt", "file"),
        MockResource("book.xlsx", "excel", "Sheet1"),
    ]
    
    request = MockRequest(app, resources)
    
    # Test with no user (unauthenticated) — no resources visible
    links = build_accessible_ui_links(request, None)
    assert len(links) == 0
    
    # Test with user having permission
    with Session(app.state.db_engine) as db:
        user = User(username="testuser", password_hash="dummy")
        db.add(user)
        db.commit()
        
        perm = Permission(resource="data", action="read")
        file_perm = Permission(resource="notes", action="read")
        db.add(perm)
        db.add(file_perm)
        db.commit()
        
        group = Group(name="testgroup")
        db.add(group)
        db.commit()
        
        ug = UserGroup(user_id=user.id, group_id=group.id)
        db.add(ug)
        gp = GroupPermission(group_id=group.id, permission_id=perm.id)
        gp_file = GroupPermission(group_id=group.id, permission_id=file_perm.id)
        db.add(gp)
        db.add(gp_file)
        db.commit()

        from adapt.permissions import PermissionChecker
        checker = PermissionChecker(db)
        assert checker.has_permission(user, "data", "read") == True

        links = build_accessible_ui_links(request, user)
        assert len(links) == 2
        names = [l["name"] for l in links]
        assert "data" in names
        assert "notes" in names
        assert "doc" not in names  # no explicit permission for the markdown resource
        file_link = next(link for link in links if link["name"] == "notes")
        assert file_link["url"] == "/notes"


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


# ---------------------------------------------------------------------------
# Media gallery RBAC tests
# ---------------------------------------------------------------------------

def _make_app_with_media(tmp_path):
    """Create an app with a fake media resource and return (app, namespace)."""
    media_file = tmp_path / "track.mp3"
    media_file.write_bytes(b"ID3" + b"\x00" * 128)  # minimal file, metadata extraction may warn
    return create_app(AdaptConfig(root=tmp_path)), "track"


def _add_user_with_media_permission(app, username, namespace):
    """Create a regular user and grant them read permission to a media namespace."""
    with Session(app.state.db_engine) as db:
        user = User(username=username, password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)

        perm = Permission(resource=namespace, action="read")
        db.add(perm)
        db.commit()
        db.refresh(perm)

        group = Group(name=f"{username}_group")
        db.add(group)
        db.commit()
        db.refresh(group)

        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
        db.commit()

        token = create_session(db, user.id)
    return token


def test_media_gallery_hides_items_without_permission(tmp_path):
    """Authenticated user with no media permissions receives 403 from the gallery."""
    app, _ = _make_app_with_media(tmp_path)
    client = TestClient(app)

    with Session(app.state.db_engine) as db:
        user = User(username="noperm", password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)

    client.cookies.set(SESSION_COOKIE, token)
    response = client.get("/ui/media", headers={"Accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 403


def test_media_gallery_shows_permitted_items(tmp_path):
    """Authenticated user with media permission sees that file in the gallery."""
    app, namespace = _make_app_with_media(tmp_path)
    client = TestClient(app)
    token = _add_user_with_media_permission(app, "reader", namespace)

    client.cookies.set(SESSION_COOKIE, token)
    response = client.get("/ui/media", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "track.mp3" in response.text


def test_media_gallery_shows_all_items_for_superuser(tmp_path):
    """Superusers see the full media gallery without needing explicit permissions."""
    app, _ = _make_app_with_media(tmp_path)

    with Session(app.state.db_engine) as db:
        admin = User(username="admin", password_hash=hash_password("admin"), is_superuser=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_session(db, admin.id)

    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)
    response = client.get("/ui/media", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "track.mp3" in response.text


def test_root_nav_omits_media_gallery_without_permission(tmp_path):
    """Landing page nav does not include the Media Gallery link when the user has no media perms."""
    app, _ = _make_app_with_media(tmp_path)
    client = TestClient(app)

    with Session(app.state.db_engine) as db:
        user = User(username="noperm2", password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)

    client.cookies.set(SESSION_COOKIE, token)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "Media Gallery" not in response.text


def test_root_nav_includes_media_gallery_with_permission(tmp_path):
    """Landing page nav includes the Media Gallery link when the user has at least one media perm."""
    app, namespace = _make_app_with_media(tmp_path)
    client = TestClient(app)
    token = _add_user_with_media_permission(app, "reader2", namespace)

    client.cookies.set(SESSION_COOKIE, token)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "Media Gallery" in response.text


def _grant_read_permission(app, username, namespace):
    """Create a regular user and grant them read permission to one namespace only."""
    with Session(app.state.db_engine) as db:
        user = User(username=username, password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)

        perm = Permission(resource=namespace, action="read")
        db.add(perm)
        db.commit()
        db.refresh(perm)

        group = Group(name=f"{username}_group")
        db.add(group)
        db.commit()
        db.refresh(group)

        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
        db.commit()

        token = create_session(db, user.id)
    return token


def test_dataset_ui_nav_omits_resources_without_permission(tmp_path):
    """A dataset UI page's nav dropdown must not leak the names of other
    datasets the viewing user has no read permission on."""
    (tmp_path / "public.csv").write_text("name,age\nAlice,30")
    (tmp_path / "secret.csv").write_text("name,age\nBob,25")
    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    app = create_app(config)
    if not hasattr(app.state, "lock_manager"):
        app.state.lock_manager = LockManager(engine)

    token = _grant_read_permission(app, "reader3", "public")
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)

    response = client.get("/ui/public/")
    assert response.status_code == 200
    assert "secret" not in response.text
    assert "public" in response.text


def test_markdown_page_nav_omits_resources_without_permission(tmp_path):
    """A markdown page's nav dropdown must not leak the names of other
    resources the viewing user has no read permission on."""
    (tmp_path / "notes.md").write_text("# Notes\n")
    (tmp_path / "secret.csv").write_text("name,age\nBob,25")
    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    app = create_app(config)
    if not hasattr(app.state, "lock_manager"):
        app.state.lock_manager = LockManager(engine)

    token = _grant_read_permission(app, "reader4", "notes")
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)

    response = client.get("/notes", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "secret" not in response.text


def test_openapi_hides_media_gallery_without_media_permission(tmp_path):
    """OpenAPI schema omits /ui/media for users with no accessible media resources."""
    app, _ = _make_app_with_media(tmp_path)
    client = TestClient(app)

    with Session(app.state.db_engine) as db:
        user = User(username="noperm3", password_hash=hash_password("pass"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)

    client.cookies.set(SESSION_COOKIE, token)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/ui/media" not in paths


def test_openapi_includes_media_gallery_with_media_permission(tmp_path):
    """OpenAPI schema includes /ui/media only for users with at least one media permission."""
    app, namespace = _make_app_with_media(tmp_path)
    client = TestClient(app)
    token = _add_user_with_media_permission(app, "reader3", namespace)

    client.cookies.set(SESSION_COOKIE, token)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/ui/media" in paths


