from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable
import logging
import json
import os
import sys

from adapt import __version__ as adapt_version
logger = logging.getLogger(__name__)


@dataclass
class AdaptConfig:
    """Configuration class for the Adapt application.

    Attributes:
        root: The root directory path for the application.
        readonly: Whether the application is in read-only mode.
        version: The version of the application.
        tls_cert: Path to the TLS certificate file.
        tls_key: Path to the TLS key file.
        secure_cookies: Whether to set secure flags on cookies.
        plugin_registry: Mapping of file extensions to plugin class paths.
        logging: Logging configuration dictionary for dictConfig.
    """
    root: Path
    host: str = "127.0.0.1"
    port: int = 8000
    readonly: bool = False
    debug: bool = False
    version: str = adapt_version
    tls_cert: Path | None = None
    tls_key: Path | None = None
    secure_cookies: bool = False  # Whether to set secure flag on cookies
    plugin_registry: dict[str, str] = field(default_factory=lambda: {
        ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
        ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
        ".xls": "adapt.plugins.excel_plugin.ExcelPlugin",
        ".parquet": "adapt.plugins.parquet_plugin.ParquetPlugin",
        ".py": "adapt.plugins.python_plugin.PythonHandlerPlugin",
        ".html": "adapt.plugins.html_plugin.HtmlPlugin",
        ".txt": "adapt.plugins.html_plugin.HtmlPlugin",
        ".md": "adapt.plugins.markdown_plugin.MarkdownPlugin",
        ".mp4": "adapt.plugins.media_plugin.MediaPlugin",
        ".mp3": "adapt.plugins.media_plugin.MediaPlugin",
        ".avi": "adapt.plugins.media_plugin.MediaPlugin",
        ".mkv": "adapt.plugins.media_plugin.MediaPlugin",
        ".webm": "adapt.plugins.media_plugin.MediaPlugin",
        ".ogg": "adapt.plugins.media_plugin.MediaPlugin",
        ".wav": "adapt.plugins.media_plugin.MediaPlugin",
    })
    logging: dict[str, Any] = field(default_factory=lambda: {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout"
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"]
        }
    })

    def __post_init__(self) -> None:
        """Post-initialization to resolve paths and set database path."""
        self.root = self.root.resolve()
        self.db_path = self.root / ".adapt" / "adapt.db"
        logger.debug("Config initialized: root=%s, db_path=%s, readonly=%s", self.root, self.db_path, self.readonly)

    @staticmethod
    def _parse_env_bool(value: str, key: str) -> bool:
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        logger.error("Invalid boolean value for %s: %s", key, value)
        sys.exit(1)

    def get_plugin_factory(self, extension: str) -> Callable[..., Any]:
        """Get the plugin factory for a given file extension.

        Args:
            extension: The file extension (e.g., '.csv').

        Returns:
            The plugin class factory.

        Raises:
            ValueError: If no plugin is registered for the extension.
        """
        normalized = extension.lower()
        dotted = self.plugin_registry.get(normalized)
        if not dotted:
            logger.error("No plugin registered for extension '%s'", extension)
            raise ValueError(f"No plugin registered for '{extension}'")

        module_name, class_name = dotted.rsplit(".", 1)
        module = import_module(module_name)
        plugin_cls = getattr(module, class_name)
        logger.debug("Loaded plugin %s for extension '%s'", dotted, extension)
        return plugin_cls

    def load_from_file(self) -> None:
        """Load configuration from DOCROOT/.adapt/conf.json, creating it with defaults if missing."""
        conf_path = self.root / ".adapt" / "conf.json"
        (self.root / ".adapt").mkdir(parents=True, exist_ok=True)
        self._ensure_config_file(conf_path)
        data = self._read_config_file(conf_path)
        self._validate_config(data, conf_path)
        self._apply_file_config(data)
        self._apply_env_overrides()
        if self.debug:
            self.logging.setdefault("root", {})
            self.logging["root"]["level"] = "DEBUG"

    def _ensure_config_file(self, conf_path: Path) -> None:
        """Write conf.json with current defaults if it does not yet exist."""
        if conf_path.exists():
            return
        defaults = {
            "plugin_registry": self.plugin_registry.copy(),
            "host": self.host,
            "port": self.port,
            "tls_cert": str(self.tls_cert) if self.tls_cert else None,
            "tls_key": str(self.tls_key) if self.tls_key else None,
            "secure_cookies": self.secure_cookies,
            "readonly": self.readonly,
            "debug": self.debug,
            "logging": self.logging.copy(),
        }
        with conf_path.open("w") as f:
            json.dump(defaults, f, indent=2)

    def _read_config_file(self, conf_path: Path) -> dict:
        """Read and JSON-parse conf.json, exiting on parse error."""
        try:
            with conf_path.open() as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", conf_path, e)
            sys.exit(1)

    def _validate_config(self, data: dict, conf_path: Path) -> None:
        """Validate all keys and types in the loaded config dict, exiting on error."""
        allowed_keys = {
            "plugin_registry", "host", "port", "tls_cert", "tls_key",
            "secure_cookies", "readonly", "debug", "logging",
        }
        for key in data:
            if key not in allowed_keys:
                logger.error("Unknown key in %s: %s", conf_path, key)
                sys.exit(1)

        if "plugin_registry" in data:
            if not isinstance(data["plugin_registry"], dict):
                logger.error("plugin_registry must be a dict")
                sys.exit(1)
            for ext, path in data["plugin_registry"].items():
                if not isinstance(ext, str) or not isinstance(path, str):
                    logger.error("plugin_registry values must be str: str")
                    sys.exit(1)
        if "host" in data and not isinstance(data["host"], str):
            logger.error("host must be str")
            sys.exit(1)
        if "port" in data:
            if not isinstance(data["port"], int):
                logger.error("port must be int")
                sys.exit(1)
            if not (1 <= data["port"] <= 65535):
                logger.error("port must be between 1 and 65535")
                sys.exit(1)
        if "tls_cert" in data and data["tls_cert"] is not None:
            if not isinstance(data["tls_cert"], str):
                logger.error("tls_cert must be str or null")
                sys.exit(1)
        if "tls_key" in data and data["tls_key"] is not None:
            if not isinstance(data["tls_key"], str):
                logger.error("tls_key must be str or null")
                sys.exit(1)
        for bool_key in ("secure_cookies", "readonly", "debug"):
            if bool_key in data and not isinstance(data[bool_key], bool):
                logger.error("%s must be bool", bool_key)
                sys.exit(1)
        if "logging" in data and not isinstance(data["logging"], dict):
            logger.error("logging must be a dict")
            sys.exit(1)

    def _apply_file_config(self, data: dict) -> None:
        """Merge validated file config dict into this instance."""
        if "plugin_registry" in data:
            self.plugin_registry.update(data["plugin_registry"])
        if "host" in data:
            self.host = data["host"]
        if "port" in data:
            self.port = data["port"]
        if "tls_cert" in data and data["tls_cert"]:
            self.tls_cert = Path(data["tls_cert"])
        if "tls_key" in data and data["tls_key"]:
            self.tls_key = Path(data["tls_key"])
        if "secure_cookies" in data:
            self.secure_cookies = data["secure_cookies"]
        if "readonly" in data:
            self.readonly = data["readonly"]
        if "debug" in data:
            self.debug = data["debug"]
        if "logging" in data:
            self.logging.update(data["logging"])

    def _apply_env_overrides(self) -> None:
        """Apply ADAPT_* environment variable overrides to this instance."""
        if "ADAPT_HOST" in os.environ:
            self.host = os.environ["ADAPT_HOST"]
        if "ADAPT_PORT" in os.environ:
            try:
                port = int(os.environ["ADAPT_PORT"])
            except ValueError:
                logger.error("ADAPT_PORT must be an integer")
                sys.exit(1)
            if not (1 <= port <= 65535):
                logger.error("ADAPT_PORT must be between 1 and 65535")
                sys.exit(1)
            self.port = port
        if "ADAPT_READONLY" in os.environ:
            self.readonly = self._parse_env_bool(os.environ["ADAPT_READONLY"], "ADAPT_READONLY")
        if "ADAPT_DEBUG" in os.environ:
            self.debug = self._parse_env_bool(os.environ["ADAPT_DEBUG"], "ADAPT_DEBUG")
