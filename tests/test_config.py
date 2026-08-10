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
            "host": "127.0.0.1",
            "port": 8000,
            "tls_cert": None,
            "tls_key": None,
            "secure_cookies": False,
            "search_on_startup": True,
            "readonly": False,
            "debug": False,
            "mcp_enabled": True,
            "upload": {
                "enabled": False,
                "max_size_bytes": 10 * 1024 * 1024,
                "allowed_extensions": [],
                "denied_extensions": [],
                "strict_mime_sniffing": False,
                "allowed_mime_types": [],
                "collision_policy": "overwrite",
            },
            "logging": config.logging.copy(),
        }
        assert data == expected

    def test_load_from_file_loads_and_merges(self, tmp_path):
        """Test that load_from_file loads existing conf.json and merges."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        custom_data = {
            "plugin_registry": {".test": "test.TestPlugin"},
            "host": "0.0.0.0",
            "port": 9001,
            "tls_cert": "/path/to/cert.pem",
            "tls_key": "/path/to/key.pem",
            "secure_cookies": True,
            "debug": True,
            "upload": {
                "enabled": True,
                "max_size_bytes": 12345,
                "allowed_extensions": [".txt"],
                "strict_mime_sniffing": True,
                "allowed_mime_types": ["text/plain"],
                "collision_policy": "reject",
            },
            "logging": {"root": {"level": "DEBUG"}},
        }
        with conf_path.open('w') as f:
            json.dump(custom_data, f)

        config = AdaptConfig(root=tmp_path)
        config.load_from_file()

        assert config.plugin_registry[".test"] == "test.TestPlugin"
        assert config.host == "0.0.0.0"
        assert config.port == 9001
        assert config.tls_cert == Path("/path/to/cert.pem")
        assert config.tls_key == Path("/path/to/key.pem")
        assert config.secure_cookies is True
        assert config.debug is True
        assert config.upload["enabled"] is True
        assert config.upload["max_size_bytes"] == 12345
        assert config.upload["allowed_extensions"] == [".txt"]
        assert config.upload["strict_mime_sniffing"] is True
        assert config.upload["allowed_mime_types"] == ["text/plain"]
        assert config.upload["collision_policy"] == "reject"
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

    def test_load_from_file_invalid_type_readonly(self, tmp_path, caplog):
        """Test that invalid readonly type causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        data = {"readonly": "not_a_bool"}
        with conf_path.open('w') as f:
            json.dump(data, f)

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "readonly must be bool" in caplog.text

    def test_load_from_file_invalid_type_host(self, tmp_path, caplog):
        """Test that invalid host type causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        data = {"host": 123}
        with conf_path.open('w') as f:
            json.dump(data, f)

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "host must be str" in caplog.text

    def test_load_from_file_invalid_type_port(self, tmp_path, caplog):
        """Test that invalid port type causes exit."""
        conf_path = tmp_path / ".adapt" / "conf.json"
        conf_path.parent.mkdir(parents=True)
        data = {"port": "8000"}
        with conf_path.open('w') as f:
            json.dump(data, f)

        config = AdaptConfig(root=tmp_path)
        with pytest.raises(SystemExit):
            config.load_from_file()

        assert "port must be int" in caplog.text

    def test_env_overrides_applied(self, tmp_path, monkeypatch):
        """Test that environment variables override file/default config values."""
        monkeypatch.setenv("ADAPT_HOST", "0.0.0.0")
        monkeypatch.setenv("ADAPT_PORT", "8123")
        monkeypatch.setenv("ADAPT_READONLY", "true")
        monkeypatch.setenv("ADAPT_DEBUG", "1")
        monkeypatch.setenv("ADAPT_UPLOAD_ENABLED", "true")
        monkeypatch.setenv("ADAPT_UPLOAD_MAX_SIZE_BYTES", "2048")
        monkeypatch.setenv("ADAPT_UPLOAD_ALLOWED_EXTENSIONS", ".txt,.md")
        monkeypatch.setenv("ADAPT_UPLOAD_DENIED_EXTENSIONS", ".exe,.dll")
        monkeypatch.setenv("ADAPT_UPLOAD_STRICT_MIME_SNIFFING", "true")
        monkeypatch.setenv("ADAPT_UPLOAD_ALLOWED_MIME_TYPES", "text/plain,application/json")
        monkeypatch.setenv("ADAPT_UPLOAD_COLLISION_POLICY", "reject")

        config = AdaptConfig(root=tmp_path)
        config.load_from_file()

        assert config.host == "0.0.0.0"
        assert config.port == 8123
        assert config.readonly is True
        assert config.debug is True
        assert config.upload["enabled"] is True
        assert config.upload["max_size_bytes"] == 2048
        assert config.upload["allowed_extensions"] == [".txt", ".md"]
        assert config.upload["denied_extensions"] == [".exe", ".dll"]
        assert config.upload["strict_mime_sniffing"] is True
        assert config.upload["allowed_mime_types"] == ["text/plain", "application/json"]
        assert config.upload["collision_policy"] == "reject"
        assert config.logging["root"]["level"] == "DEBUG"