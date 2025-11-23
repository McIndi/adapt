import tempfile
from pathlib import Path

import pytest

from adapt.plugins.markdown_plugin import MarkdownPlugin
from adapt.plugins.base import ResourceDescriptor

from fastapi import Request, APIRouter
from fastapi.testclient import TestClient


@pytest.fixture
def sample_md():
    """Create a temporary Markdown file for testing."""
    content = "# Test\n\nThis is a test."
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        path = Path(f.name)
    yield path
    path.unlink()


def test_markdown_plugin_detect(sample_md):
    plugin = MarkdownPlugin()
    assert plugin.detect(sample_md)
    assert not plugin.detect(Path("test.txt"))


def test_markdown_plugin_load(sample_md):
    plugin = MarkdownPlugin()
    descriptor = plugin.load(sample_md)
    assert isinstance(descriptor, ResourceDescriptor)
    assert descriptor.path == sample_md
    assert descriptor.resource_type == "markdown"


def test_markdown_plugin_schema(sample_md):
    plugin = MarkdownPlugin()
    descriptor = plugin.load(sample_md)
    schema = plugin.schema(descriptor)
    assert schema == {}


def test_markdown_plugin_read(sample_md):
    plugin = MarkdownPlugin()
    descriptor = plugin.load(sample_md)
    request = Request(scope={"type": "http", "method": "GET", "path": "/"})
    content = plugin.read(descriptor, request)
    assert "<h1>Test</h1>" in content
    assert "<p>This is a test.</p>" in content
    assert "<!DOCTYPE html>" in content


def test_markdown_plugin_write_raises(sample_md):
    plugin = MarkdownPlugin()
    descriptor = plugin.load(sample_md)
    with pytest.raises(NotImplementedError):
        plugin.write(descriptor, {}, None, None)


def test_markdown_plugin_get_route_configs(sample_md):
    plugin = MarkdownPlugin()
    descriptor = plugin.load(sample_md)
    configs = plugin.get_route_configs(descriptor)
    assert len(configs) == 1
    prefix, router = configs[0]
    assert prefix == ""
    assert isinstance(router, APIRouter)
    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == ""
    assert route.methods == {"GET"}