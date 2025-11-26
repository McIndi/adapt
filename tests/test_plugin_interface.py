import pytest
from pathlib import Path
from adapt.plugins.base import Plugin, ResourceDescriptor
from adapt.plugins.csv_plugin import CsvPlugin
from adapt.plugins.excel_plugin import ExcelPlugin
from adapt.plugins.html_plugin import HtmlPlugin
from adapt.plugins.markdown_plugin import MarkdownPlugin
from adapt.plugins.media_plugin import MediaPlugin
from adapt.plugins.python_plugin import PythonHandlerPlugin

# List of all plugin classes to test
PLUGIN_CLASSES = [
    CsvPlugin,
    ExcelPlugin,
    HtmlPlugin,
    MarkdownPlugin,
    MediaPlugin,
    PythonHandlerPlugin,
]

@pytest.mark.parametrize("plugin_cls", PLUGIN_CLASSES)
def test_plugin_implements_interface(plugin_cls):
    """Verify that all plugins implement the abstract base class correctly."""
    assert issubclass(plugin_cls, Plugin)
    # Instantiate to check for abstract method implementation
    plugin = plugin_cls()
    assert isinstance(plugin, Plugin)

@pytest.mark.parametrize("plugin_cls", PLUGIN_CLASSES)
def test_plugin_methods_signature(plugin_cls):
    """Verify that plugins have the required methods with correct signatures."""
    plugin = plugin_cls()
    
    assert hasattr(plugin, "detect")
    assert hasattr(plugin, "load")
    assert hasattr(plugin, "schema")
    assert hasattr(plugin, "read")
    assert hasattr(plugin, "write")
    assert hasattr(plugin, "get_route_configs")

def test_resource_descriptor_structure():
    """Verify ResourceDescriptor structure."""
    path = Path("test.csv")
    descriptor = ResourceDescriptor(
        path=path,
        resource_type="csv",
        metadata={"key": "value"}
    )
    
    assert descriptor.path == path
    assert descriptor.resource_type == "csv"
    assert descriptor.metadata == {"key": "value"}
    assert descriptor.schema_path is None
    assert descriptor.ui_path is None
