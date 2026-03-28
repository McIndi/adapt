from pathlib import Path
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from adapt.app import create_app
from adapt.config import AdaptConfig
from adapt.storage import User
from adapt.auth.password import hash_password
from adapt.auth.session import create_session, SESSION_COOKIE
from adapt.security import CSRF_COOKIE_NAME, generate_csrf_token
from sqlmodel import Session
import tempfile


def _route_signatures(app):
    signatures = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods):
            signatures.append(f"{method} {route.path}")
    return sorted(signatures)


def _dispose_app(app):
    app.state.db_engine.dispose()


def _make_superuser_client(app):
    with Session(app.state.db_engine) as db:
        admin = User(username="admin", password_hash=hash_password("admin"), is_superuser=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_session(db, admin.id)

    client = TestClient(app)
    csrf_token = generate_csrf_token()
    client.cookies.set(SESSION_COOKIE, token)
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
    return client, csrf_token


class TestReadonlyMode:
    """Test readonly mode functionality across the application."""

    def test_readonly_mode_disables_dataset_write_routes(self):
        """Test that readonly mode keeps dataset write endpoints mounted but blocks writes."""
        # Create a temporary directory with a CSV file
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            csv_file = tmp_path / "test.csv"
            csv_file.write_text("id,name,value\n1,test,100\n")

            # Test with readonly=False (normal mode)
            config = AdaptConfig(root=tmp_path, readonly=False)
            app = create_app(config)
            app_readonly = None
            try:
                routes = _route_signatures(app)

                # Should have write routes
                assert any("POST /api/test" in route for route in routes), "POST route should exist in normal mode"
                assert any("PATCH /api/test" in route for route in routes), "PATCH route should exist in normal mode"
                assert any("DELETE /api/test" in route for route in routes), "DELETE route should exist in normal mode"

                # Test with readonly=True
                config_readonly = AdaptConfig(root=tmp_path, readonly=True)
                app_readonly = create_app(config_readonly)

                routes_readonly = _route_signatures(app_readonly)
                client, csrf_token = _make_superuser_client(app_readonly)

                # Routes remain mounted in readonly mode, but writes are blocked at request time.
                assert any("POST /api/test" in route for route in routes_readonly), "POST route should remain mounted in readonly mode"
                assert any("PATCH /api/test" in route for route in routes_readonly), "PATCH route should remain mounted in readonly mode"
                assert any("DELETE /api/test" in route for route in routes_readonly), "DELETE route should remain mounted in readonly mode"

                # Should still have read routes
                assert any("GET /api/test" in route for route in routes_readonly), "GET route should still exist in readonly mode"

                headers = {"X-CSRF-Token": csrf_token}
                response = client.post("/api/test", json={"action": "create", "data": [{"id": 2, "name": "next", "value": 200}]}, headers=headers)
                assert response.status_code == 405

                response = client.patch("/api/test", json={"action": "update", "data": {"_row_id": 1, "value": 101}}, headers=headers)
                assert response.status_code == 405

                response = client.request("DELETE", "/api/test", json={"action": "delete", "data": {"_row_id": 1}}, headers=headers)
                assert response.status_code == 405
            finally:
                _dispose_app(app)
                if app_readonly is not None:
                    _dispose_app(app_readonly)

    def test_readonly_mode_preserves_read_routes(self):
        """Test that readonly mode preserves all read-only routes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            csv_file = tmp_path / "test.csv"
            csv_file.write_text("id,name,value\n1,test,100\n")

            config = AdaptConfig(root=tmp_path, readonly=True)
            app = create_app(config)
            try:
                routes = _route_signatures(app)

                # Should preserve schema routes
                assert any("GET /schema/test" in route for route in routes), "Schema routes should exist in readonly mode"

                # Should preserve UI routes
                assert any("GET /ui/test" in route for route in routes), "UI routes should exist in readonly mode"

                # Should preserve health endpoint
                assert any("GET /health" in route for route in routes), "Health endpoint should exist in readonly mode"

                # Should preserve auth routes (login/logout are read operations in a sense)
                assert any("POST /auth/login" in route for route in routes), "Login should work in readonly mode"
                assert any("POST /auth/logout" in route for route in routes), "Logout should work in readonly mode"
            finally:
                _dispose_app(app)