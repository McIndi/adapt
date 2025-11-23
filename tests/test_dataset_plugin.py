import pytest
from pathlib import Path
from adapt.plugins.dataset_plugin import DatasetPlugin, ResourceDescriptor, PluginContext
from adapt.plugins.base import Plugin
from fastapi import Request, APIRouter
from adapt.locks import LockManager
from sqlalchemy import create_engine

class MockDatasetPlugin(DatasetPlugin):
    """Concrete implementation for testing abstract DatasetPlugin."""
    def detect(self, path: Path) -> bool:
        return True
        
    def _get_header_and_sample(self, path: Path):
        return ["name", "age"], ["Alice", "30"]
        
    def _read_raw_rows(self, resource: ResourceDescriptor):
        return [["Alice", "30"], ["Bob", "25"]]
        
    def _write_rows(self, resource: ResourceDescriptor, rows, header):
        self.last_written_rows = rows

    @property
    def resource_type(self):
        return "mock"

@pytest.fixture
def mock_plugin():
    return MockDatasetPlugin()

@pytest.fixture
def descriptor(tmp_path):
    return ResourceDescriptor(
        path=tmp_path / "test.mock",
        resource_type="mock",
        metadata={"header": ["name", "age"], "sample_row": ["Alice", "30"], "primary_key": "_row_id"}
    )

def test_schema_inference(mock_plugin, descriptor):
    schema = mock_plugin.schema(descriptor)
    assert schema["type"] == "object"
    assert schema["primary_key"] == "_row_id"
    assert schema["columns"]["name"]["type"] == "string"
    assert schema["columns"]["age"]["type"] == "integer"

def test_read_casting(mock_plugin, descriptor):
    # Mock request
    request = Request(scope={"type": "http", "method": "GET", "path": "/"})
    
    rows = mock_plugin.read(descriptor, request)
    
    assert len(rows) == 2
    assert rows[0] == {"_row_id": 1, "name": "Alice", "age": 30}
    assert rows[1] == {"_row_id": 2, "name": "Bob", "age": 25}
    assert isinstance(rows[0]["age"], int)

def test_write_create(mock_plugin, descriptor, tmp_path):
    from adapt.storage import init_database
    
    # Mock context
    db_path = tmp_path / 'test.db'
    engine = init_database(db_path)  # Creates all tables
    lock_manager = LockManager(engine)
    context = PluginContext(engine=engine, root=tmp_path, readonly=False, lock_manager=lock_manager)
    request = Request(scope={"type": "http", "method": "POST", "path": "/"})
    
    data = {
        "action": "create",
        "data": [{"name": "Charlie", "age": 35}]
    }
    
    mock_plugin.write(descriptor, data, request, context)
    
    assert len(mock_plugin.last_written_rows) == 3
    assert mock_plugin.last_written_rows[-1]["name"] == "Charlie"
    assert mock_plugin.last_written_rows[-1]["_row_id"] == 3

def test_write_update(mock_plugin, descriptor, tmp_path):
    from adapt.storage import init_database
    
    db_path = tmp_path / 'test.db'
    engine = init_database(db_path)
    lock_manager = LockManager(engine)
    context = PluginContext(engine=engine, root=tmp_path, readonly=False, lock_manager=lock_manager)
    request = Request(scope={"type": "http", "method": "PATCH", "path": "/"})
    
    data = {
        "action": "update",
        "data": {"_row_id": 1, "age": 31}
    }
    
    mock_plugin.write(descriptor, data, request, context)
    
    updated_row = next(r for r in mock_plugin.last_written_rows if r["_row_id"] == 1)
    assert updated_row["age"] == 31
    assert updated_row["name"] == "Alice"  # Unchanged

def test_write_delete(mock_plugin, descriptor, tmp_path):
    from adapt.storage import init_database
    
    db_path = tmp_path / 'test.db'
    engine = init_database(db_path)
    lock_manager = LockManager(engine)
    context = PluginContext(engine=engine, root=tmp_path, readonly=False, lock_manager=lock_manager)
    request = Request(scope={"type": "http", "method": "DELETE", "path": "/"})
    
    data = {
        "action": "delete",
        "data": {"_row_id": 2}
    }
    
    mock_plugin.write(descriptor, data, request, context)
    
    assert len(mock_plugin.last_written_rows) == 1
    assert mock_plugin.last_written_rows[0]["name"] == "Alice"

def test_get_route_configs(mock_plugin, descriptor):
    configs = mock_plugin.get_route_configs(descriptor)
    
    prefixes = {c[0] for c in configs}
    assert "api" in prefixes
    assert "schema" in prefixes
    assert "ui" in prefixes
    
    # Verify routers are attached
    for prefix, router in configs:
        assert isinstance(router, APIRouter)
