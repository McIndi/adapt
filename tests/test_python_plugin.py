from pathlib import Path

from adapt.plugins.python_plugin import PythonHandlerPlugin


def test_python_plugin_skips_modules_with_import_errors(tmp_path):
    handler = tmp_path / "bad_handler.py"
    handler.write_text("from .storage import APIKey\n", encoding="utf-8")

    plugin = PythonHandlerPlugin()
    descriptor = plugin.load(handler)

    configs = plugin.get_route_configs(descriptor)
    assert configs == []
