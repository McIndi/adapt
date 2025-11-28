import json
import pytest
from pathlib import Path
from adapt.config import AdaptConfig


class TestAdaptConfig:
    def test_load_from_file_creates_default(self, tmp_path):
        """Test that load_from_file creates conf.json with defaults if missing."""
        config = AdaptConfig(root=tmp_path)
        config.load_from_file()

        conf_path = tmp_path / ".adapt" / "conf.json"
        assert conf_path.exists()

        with conf_path.open() as f:
            data = json.load(f)

        expected = {
            "plugin_registry": config.plugin_registry.copy(),
            "tls_cert": None,
            "tls_key": None,
            "secure_cookies": False,
            "logging": config.logging.copy(),
        }
        assert data == expected

    def test_load_from_file_loads_and_merges(self, tmp_path):
        """Test that load_from_file loads existing conf.json and merges."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        custom_data = {
            "plugin_registry": {".test": "test.TestPlugin"},
            "tls_cert": "/path/to/cert.pem",
            "tls_key": "/path/to/key.pem",
            "secure_cookies": True,
            "logging": {"root": {"level": "DEBUG"}},
        }
        with conf_path.open('w') as f:
            json.dump(custom_data, f)

        config = AdaptConfig(root=tmp_path)
        config.load_from_file()

        assert config.plugin_registry[".test"] == "test.TestPlugin"
        assert config.tls_cert == Path("/path/to/cert.pem")
        assert config.tls_key == Path("/path/to/key.pem")
        assert config.secure_cookies is True
        assert config.logging["root"]["level"] == "DEBUG"

    def test_load_from_file_invalid_json(self, tmp_path, caplog):
        """Test that invalid JSON causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        with conf_path.open('w') as f:
            f.write("{ invalid json")

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "Invalid JSON" in caplog.text

    def test_load_from_file_unknown_key(self, tmp_path, caplog):
        """Test that unknown key causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        data = {"unknown_key": "value"}
        with conf_path.open('w') as f:
            json.dump(data, f)

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "Unknown key" in caplog.text

    def test_load_from_file_invalid_type_plugin_registry(self, tmp_path, caplog):
        """Test that invalid plugin_registry type causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        data = {"plugin_registry": "not_a_dict"}
        with conf_path.open('w') as f:
            json.dump(data, f)

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "must be a dict" in caplog.text

    def test_load_from_file_invalid_type_secure_cookies(self, tmp_path, caplog):
        """Test that invalid secure_cookies type causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        data = {"secure_cookies": "not_a_bool"}
        with conf_path.open('w') as f:
            json.dump(data, f)

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "must be bool" in caplog.text

    def test_load_from_file_invalid_type_logging(self, tmp_path, caplog):
        """Test that invalid logging type causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        data = {"logging": "not_a_dict"}
        with conf_path.open('w') as f:
            json.dump(data, f)

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "logging must be a dict" in caplog.text