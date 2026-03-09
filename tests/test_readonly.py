import pytest
from pathlib import Path
from adapt.app import create_app
from adapt.config import AdaptConfig
import tempfile
import os


class TestReadonlyMode:
    """Test readonly mode functionality across the application."""

    def test_readonly_mode_disables_dataset_write_routes(self):
        """Test that readonly mode prevents creation of dataset write routes."""
        # Create a temporary directory with a CSV file
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            csv_file = tmp_path / "test.csv"
            csv_file.write_text("id,name,value\n1,test,100\n")

            # Test with readonly=False (normal mode)
            config = AdaptConfig(root=tmp_path, readonly=False)
            app = create_app(config)

            routes = [f"{route.methods} {route.path}" for route in app.routes if hasattr(route, 'path')]
            routes.sort()

            # Should have write routes
            assert any("POST /api/test" in route for route in routes), "POST route should exist in normal mode"
            assert any("PATCH /api/test" in route for route in routes), "PATCH route should exist in normal mode"
            assert any("DELETE /api/test" in route for route in routes), "DELETE route should exist in normal mode"

            # Test with readonly=True
            config_readonly = AdaptConfig(root=tmp_path, readonly=True)
            app_readonly = create_app(config_readonly)

            routes_readonly = [f"{route.methods} {route.path}" for route in app_readonly.routes if hasattr(route, 'path')]
            routes_readonly.sort()

            # Should NOT have write routes
            assert not any("POST /api/test" in route for route in routes_readonly), "POST route should not exist in readonly mode"
            assert not any("PATCH /api/test" in route for route in routes_readonly), "PATCH route should not exist in readonly mode"
            assert not any("DELETE /api/test" in route for route in routes_readonly), "DELETE route should not exist in readonly mode"

            # Should still have read routes
            assert any("GET /api/test" in route for route in routes_readonly), "GET route should still exist in readonly mode"

    def test_readonly_mode_preserves_read_routes(self):
        """Test that readonly mode preserves all read-only routes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            csv_file = tmp_path / "test.csv"
            csv_file.write_text("id,name,value\n1,test,100\n")

            config = AdaptConfig(root=tmp_path, readonly=True)
            app = create_app(config)

            routes = [f"{route.methods} {route.path}" for route in app.routes if hasattr(route, 'path')]

            # Should preserve schema routes
            assert any("GET /schema/test" in route for route in routes), "Schema routes should exist in readonly mode"

            # Should preserve UI routes
            assert any("GET /ui/test" in route for route in routes), "UI routes should exist in readonly mode"

            # Should preserve health endpoint
            assert any("GET /health" in route for route in routes), "Health endpoint should exist in readonly mode"

            # Should preserve auth routes (login/logout are read operations in a sense)
            assert any("POST /auth/login" in route for route in routes), "Login should work in readonly mode"
            assert any("POST /auth/logout" in route for route in routes), "Logout should work in readonly mode"