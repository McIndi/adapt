import tempfile
from pathlib import Path

import pytest

from adapt.plugins.html_plugin import HtmlPlugin
from adapt.plugins.base import ResourceDescriptor

from fastapi import Request, APIRouter
from fastapi.testclient import TestClient


@pytest.fixture
def sample_html():
    """Create a temporary HTML file for testing."""
    content = "<html><body><h1>Test</h1></body></html>"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(content)
        path = Path(f.name)
    yield path
    path.unlink()


def test_html_plugin_detect(sample_html):
    plugin = HtmlPlugin()
    assert plugin.detect(sample_html)
    assert not plugin.detect(Path("test.txt"))


def test_html_plugin_load(sample_html):
    plugin = HtmlPlugin()
    descriptor = plugin.load(sample_html)
    assert isinstance(descriptor, ResourceDescriptor)
    assert descriptor.path == sample_html
    assert descriptor.resource_type == "html"


def test_html_plugin_schema(sample_html):
    plugin = HtmlPlugin()
    descriptor = plugin.load(sample_html)
    schema = plugin.schema(descriptor)
    assert schema == {}


def test_html_plugin_read(sample_html):
    plugin = HtmlPlugin()
    descriptor = plugin.load(sample_html)
    request = Request(scope={"type": "http", "method": "GET", "path": "/"})
    content = plugin.read(descriptor, request)
    assert content == "<html><body><h1>Test</h1></body></html>"


def test_html_plugin_write_raises(sample_html):
    plugin = HtmlPlugin()
    descriptor = plugin.load(sample_html)
    with pytest.raises(NotImplementedError):
        plugin.write(descriptor, {}, None, None)


def test_html_plugin_get_route_configs(sample_html):
    plugin = HtmlPlugin()
    descriptor = plugin.load(sample_html)
    configs = plugin.get_route_configs(descriptor)
    assert len(configs) == 1
    prefix, router = configs[0]
    assert prefix == ""
    assert isinstance(router, APIRouter)
    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == ""
    assert route.methods == {"GET"}