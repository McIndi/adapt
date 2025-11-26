import pytest
from pathlib import Path
import pandas as pd
from adapt.plugins.parquet_plugin import ParquetPlugin
from adapt.plugins.base import ResourceDescriptor

def make_parquet(tmp_path, data, columns):
    df = pd.DataFrame(data, columns=columns)
    path = tmp_path / "test.parquet"
    df.to_parquet(path, engine="fastparquet")
    return path

@pytest.fixture
def plugin():
    return ParquetPlugin()

@pytest.fixture
def resource(tmp_path):
    data = [["Alice", 30], ["Bob", 25]]
    columns = ["name", "age"]
    path = make_parquet(tmp_path, data, columns)
    # Ensure header metadata is set for schema inference
    descriptor = ResourceDescriptor(path=path, resource_type="parquet")
    descriptor.metadata["header"] = ["name", "age"]
    return descriptor

def test_detect_parquet(plugin, resource):
    assert plugin.detect(resource.path)

def test_schema(plugin, resource):
    schema = plugin.schema(resource)
    columns = schema["columns"]
    assert columns["name"]["type"] in ("object", "string")
    assert columns["age"]["type"] in ("int64", "integer", "number")

def test_read_rows(plugin, resource):
    rows = list(plugin.read_rows(resource))
    assert rows[0][0] == "Alice"
    assert rows[0][1] == 30
    assert rows[1][0] == "Bob"
    assert rows[1][1] == 25

def test_write_rows(plugin, tmp_path):
    resource = ResourceDescriptor(path=tmp_path / "write_test.parquet", resource_type="parquet")
    data = [["Charlie", 40], ["Dana", 22]]
    columns = ["name", "age"]
    plugin.write_rows(resource, data, columns)
    df = pd.read_parquet(resource.path)
    assert list(df["name"]) == ["Charlie", "Dana"]
    assert list(df["age"]) == [40, 22]
