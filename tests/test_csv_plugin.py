import csv
import errno
import tempfile
from pathlib import Path

import pytest

import adapt.cache as cache_module
import adapt.plugins.base as plugin_base
from adapt.plugins.csv_plugin import CsvPlugin
from adapt.plugins.excel_plugin import ExcelPlugin
from adapt.plugins.python_plugin import PythonHandlerPlugin
from adapt.plugins.base import ResourceDescriptor, PluginContext

from fastapi import APIRouter


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path):
    db_path = str(tmp_path / "cache.db")
    cache_module.configure(db_path)
    yield
    cache_module._db_path = None


@pytest.fixture
def sample_csv():
    """Create a temporary CSV file for testing."""
    data = [
        ["name", "age", "city"],
        ["Alice", "30", "New York"],
        ["Bob", "25", "London"],
        ["Charlie", "35", "Paris"]
    ]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
        path = Path(f.name)
    yield path
    path.unlink()


@pytest.fixture
def sample_xlsx(tmp_path):
    """Create a temporary Excel file for testing."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    data = [
        ["name", "age", "city"],
        ["Alice", "30", "New York"],
        ["Bob", "25", "London"],
        ["Charlie", "35", "Paris"]
    ]
    for row in data:
        ws.append(row)
    path = tmp_path / "test.xlsx"
    wb.save(path)
    yield path


@pytest.fixture
def csv_plugin():
    return CsvPlugin()


@pytest.fixture
def excel_plugin():
    return ExcelPlugin()


@pytest.fixture
def python_plugin():
    return PythonHandlerPlugin()


@pytest.fixture
def csv_resource_descriptor(sample_csv):
    plugin = CsvPlugin()
    return plugin.load(sample_csv)


@pytest.fixture
def excel_resource_descriptor(sample_xlsx):
    plugin = ExcelPlugin()
    descriptors = plugin.load(sample_xlsx)
    return descriptors[0]  # For testing, use the first sheet


@pytest.fixture
def sample_py(tmp_path):
    """Create a temporary Python file with a router."""
    content = '''
from fastapi import APIRouter

router = APIRouter()

@router.get("/hello")
def hello():
    return {"message": "Hello from Python handler"}
'''
    path = tmp_path / "handler.py"
    path.write_text(content)
    yield path


@pytest.fixture
def python_resource_descriptor(sample_py):
    plugin = PythonHandlerPlugin()
    return plugin.load(sample_py)


@pytest.fixture
def plugin_context(tmp_path):
    from adapt.locks import LockManager
    from adapt.storage import init_database
    
    db_path = tmp_path / 'test.db'
    engine = init_database(db_path)  # This creates all tables including lockrecord
    lock_manager = LockManager(engine)
    return PluginContext(engine=engine, root=tmp_path, readonly=False, lock_manager=lock_manager)

def test_csv_plugin_detect(csv_plugin, sample_csv):
    assert csv_plugin.detect(sample_csv)
    assert not csv_plugin.detect(Path("test.txt"))


def test_csv_plugin_load(csv_plugin, sample_csv):
    descriptor = csv_plugin.load(sample_csv)
    assert isinstance(descriptor, ResourceDescriptor)
    assert descriptor.path == sample_csv
    assert descriptor.resource_type == "csv"
    assert "header" in descriptor.metadata
    assert "sample_row" in descriptor.metadata
    assert descriptor.metadata["primary_key"] == "_row_id"


def test_csv_plugin_schema(csv_plugin, csv_resource_descriptor):
    schema = csv_plugin.schema(csv_resource_descriptor)
    assert schema["type"] == "object"
    assert schema["name"] == csv_resource_descriptor.path.stem
    assert schema["primary_key"] == "_row_id"
    assert "columns" in schema
    columns = schema["columns"]
    assert "name" in columns
    assert "age" in columns
    assert "city" in columns
    assert columns["name"]["type"] == "string"
    assert columns["age"]["type"] == "integer"
    assert columns["city"]["type"] == "string"


def test_csv_plugin_read(csv_plugin, csv_resource_descriptor):
    # This will fail until implemented
    from fastapi import Request
    request = Request(scope={"type": "http", "method": "GET", "path": "/"})
    data = csv_plugin.read(csv_resource_descriptor, request)
    assert isinstance(data, list)
    assert len(data) == 3  # 3 data rows
    assert data[0]["name"] == "Alice"
    assert data[0]["age"] == 30  # The schema indicates integer
    assert data[0]["city"] == "New York"


def test_csv_plugin_write_create(csv_plugin, csv_resource_descriptor, plugin_context):
    # Test POST - create new rows
    from fastapi import Request
    request = Request(scope={"type": "http", "method": "POST", "path": "/"})

    new_data = [
        {"name": "David", "age": 40, "city": "Berlin"},
        {"name": "Eve", "age": 28, "city": "Tokyo"}
    ]

    result = csv_plugin.write(csv_resource_descriptor, {"action": "create", "data": new_data}, request, plugin_context)
    assert result["success"] is True

    # Read back and verify
    data = csv_plugin.read(csv_resource_descriptor, request)
    assert len(data) == 5  # original 3 + 2 new
    assert data[-1]["name"] == "Eve"


def test_csv_plugin_write_update(csv_plugin, csv_resource_descriptor, plugin_context):
    # Test PATCH - update existing row
    from fastapi import Request
    request = Request(scope={"type": "http", "method": "PATCH", "path": "/"})

    update_data = {"_row_id": 1, "age": 31, "city": "Boston"}

    result = csv_plugin.write(csv_resource_descriptor, {"action": "update", "data": update_data}, request, plugin_context)
    assert result["success"] is True

    # Read back and verify
    data = csv_plugin.read(csv_resource_descriptor, request)
    alice = next(row for row in data if row["name"] == "Alice")
    assert alice["age"] == 31
    assert alice["city"] == "Boston"


def test_csv_plugin_write_delete(csv_plugin, csv_resource_descriptor, plugin_context):
    # Test DELETE - remove row
    from fastapi import Request
    request = Request(scope={"type": "http", "method": "DELETE", "path": "/"})

    delete_data = {"_row_id": 2}  # Bob

    result = csv_plugin.write(csv_resource_descriptor, {"action": "delete", "data": delete_data}, request, plugin_context)
    assert result["success"] is True

    # Read back and verify
    data = csv_plugin.read(csv_resource_descriptor, request)
    assert len(data) == 2
    names = [row["name"] for row in data]
    assert "Bob" not in names


def test_csv_plugin_write_falls_back_when_replace_raises_exdev(csv_plugin, plugin_context, tmp_path, monkeypatch):
    path = tmp_path / "cross_device.csv"
    path.write_text("name,age,city\nAlice,30,New York\n", encoding="utf-8")
    descriptor = csv_plugin.load(path)

    def raise_exdev(src, dst):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(plugin_base.os, "replace", raise_exdev)

    from fastapi import Request
    request = Request(scope={"type": "http", "method": "POST", "path": "/"})
    result = csv_plugin.write(
        descriptor,
        {"action": "create", "data": [{"name": "Bob", "age": 25, "city": "London"}]},
        request,
        plugin_context,
    )

    assert result["success"] is True
    data = csv_plugin.read(descriptor, request)
    assert [row["name"] for row in data] == ["Alice", "Bob"]


# Excel tests

def test_excel_plugin_detect(excel_plugin, sample_xlsx):
    assert excel_plugin.detect(sample_xlsx)
    assert not excel_plugin.detect(Path("test.txt"))


def test_excel_plugin_load(excel_plugin, sample_xlsx):
    descriptors = excel_plugin.load(sample_xlsx)
    assert isinstance(descriptors, list)
    assert len(descriptors) == 1  # Test xlsx has one sheet
    descriptor = descriptors[0]
    assert isinstance(descriptor, ResourceDescriptor)
    assert descriptor.path == sample_xlsx
    assert descriptor.resource_type == "excel"
    assert "header" in descriptor.metadata
    assert "sample_row" in descriptor.metadata
    assert descriptor.metadata["primary_key"] == "_row_id"


def test_excel_plugin_schema(excel_plugin, excel_resource_descriptor):
    schema = excel_plugin.schema(excel_resource_descriptor)
    assert schema["type"] == "object"
    assert schema["name"] == excel_resource_descriptor.path.stem
    assert schema["primary_key"] == "_row_id"
    assert "columns" in schema
    columns = schema["columns"]
    assert "name" in columns
    assert "age" in columns
    assert "city" in columns
    assert columns["name"]["type"] == "string"
    assert columns["age"]["type"] == "integer"
    assert columns["city"]["type"] == "string"


def test_excel_plugin_read(excel_plugin, excel_resource_descriptor):
    from fastapi import Request
    request = Request(scope={"type": "http", "method": "GET", "path": "/"})
    data = excel_plugin.read(excel_resource_descriptor, request)
    assert isinstance(data, list)
    assert len(data) == 3  # 3 data rows
    assert data[0]["name"] == "Alice"
    assert data[0]["age"] == 30  # Integers
    assert data[0]["city"] == "New York"


def test_excel_plugin_write_falls_back_when_replace_raises_exdev(
    excel_plugin,
    excel_resource_descriptor,
    plugin_context,
    monkeypatch,
):
    def raise_exdev(src, dst):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(plugin_base.os, "replace", raise_exdev)

    from fastapi import Request
    request = Request(scope={"type": "http", "method": "POST", "path": "/"})
    result = excel_plugin.write(
        excel_resource_descriptor,
        {"action": "create", "data": [{"name": "Dana", "age": 22, "city": "Tokyo"}]},
        request,
        plugin_context,
    )

    assert result["success"] is True
    data = excel_plugin.read(excel_resource_descriptor, request)
    assert data[-1]["name"] == "Dana"
    assert data[-1]["age"] == 22
    assert data[-1]["city"] == "Tokyo"


# Python handler tests

def test_python_plugin_detect(python_plugin, sample_py):
    assert python_plugin.detect(sample_py)
    assert not python_plugin.detect(Path("test.txt"))


def test_python_plugin_load(python_plugin, sample_py):
    descriptor = python_plugin.load(sample_py)
    assert isinstance(descriptor, ResourceDescriptor)
    assert descriptor.path == sample_py
    assert descriptor.resource_type == "python"


def test_python_plugin_schema(python_plugin, python_resource_descriptor):
    schema = python_plugin.schema(python_resource_descriptor)
    assert schema == {}


def test_python_plugin_get_route_configs(python_plugin, python_resource_descriptor):
    configs = python_plugin.get_route_configs(python_resource_descriptor)
    assert len(configs) == 1
    prefix, router = configs[0]
    assert prefix == "api"
    assert isinstance(router, APIRouter)
    # Check if routes are added
    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == "/hello"
    assert route.methods == {"GET"}
