import pytest
from pathlib import Path
from adapt.discovery import discover_resources, should_ignore
from adapt.config import AdaptConfig
from adapt.plugins.base import ResourceDescriptor

@pytest.fixture
def mock_config():
    config = AdaptConfig(root=Path("."))
    # Only enable CSV for simplicity in some tests
    config.plugin_registry = {".csv": "adapt.plugins.csv_plugin.CsvPlugin"}
    return config

def test_should_ignore():
    assert should_ignore(Path(".git"))
    assert should_ignore(Path(".adapt"))
    assert should_ignore(Path("subdir/.adapt"))
    assert should_ignore(Path(".env"))
    assert should_ignore(Path("project/.venv/Lib/site-packages/adapt/api_keys.py"))
    assert not should_ignore(Path("data.csv"))
    assert not should_ignore(Path("subdir/data.csv"))

def test_discover_resources_ignores_dotfiles(tmp_path, mock_config):
    (tmp_path / ".hidden.csv").touch()
    (tmp_path / "visible.csv").touch()
    
    resources = discover_resources(tmp_path, mock_config)
    
    assert len(resources) == 1
    assert resources[0].path.name == "visible.csv"

def test_discover_resources_ignores_adapt_dir(tmp_path, mock_config):
    adapt_dir = tmp_path / ".adapt"
    adapt_dir.mkdir()
    (adapt_dir / "ignored.csv").touch()
    (tmp_path / "visible.csv").touch()
    
    resources = discover_resources(tmp_path, mock_config)
    
    assert len(resources) == 1
    assert resources[0].path.name == "visible.csv"

def test_discover_resources_generates_companion_files(tmp_path, mock_config):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\nAlice,30")
    
    resources = discover_resources(tmp_path, mock_config)
    
    assert len(resources) == 1
    resource = resources[0]
    
    # Check companion files exist in .adapt
    adapt_dir = tmp_path / ".adapt"
    assert adapt_dir.exists()
    assert (adapt_dir / "data.schema.json").exists()
    assert (adapt_dir / "data.index.html").exists()
    
    # Check resource paths point to them
    assert resource.schema_path == adapt_dir / "data.schema.json"
    assert resource.ui_path == adapt_dir / "data.index.html"

def test_discover_resources_nested_structure(tmp_path, mock_config):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "data.csv").write_text("name,age\nBob,25")
    
    resources = discover_resources(tmp_path, mock_config)
    
    assert len(resources) == 1

    # Check companion files mirror structure in .adapt
    adapt_subdir = tmp_path / ".adapt" / "subdir"
    assert adapt_subdir.exists()
    assert (adapt_subdir / "data.schema.json").exists()

def test_discover_resources_unsupported_extension(tmp_path, mock_config):
    (tmp_path / "data.txt").touch()
    resources = discover_resources(tmp_path, mock_config)
    assert len(resources) == 0


def test_discover_resources_calls_plugin_detect_before_load(tmp_path, mock_config, monkeypatch):
    candidate = tmp_path / "data.csv"
    candidate.write_text("not,really,csv")

    class RejectingPlugin:
        detect_calls = []
        load_calls = []

        def detect(self, path):
            self.detect_calls.append(path)
            return False

        def load(self, path):
            self.load_calls.append(path)
            return ResourceDescriptor(path=path, resource_type="test")

    monkeypatch.setattr(mock_config, "get_plugin_factory", lambda extension: RejectingPlugin)

    resources = discover_resources(tmp_path, mock_config)

    assert resources == []
    assert RejectingPlugin.detect_calls == [candidate]
    assert RejectingPlugin.load_calls == []
    assert not (tmp_path / ".adapt").exists()
