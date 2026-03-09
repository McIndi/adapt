from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable
import logging
import json
import sys

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
    readonly: bool = False
    version: str = "0.1.0"
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
        if not conf_path.exists():
            defaults = {
                "plugin_registry": self.plugin_registry.copy(),
                "tls_cert": str(self.tls_cert) if self.tls_cert else None,
                "tls_key": str(self.tls_key) if self.tls_key else None,
                "secure_cookies": self.secure_cookies,
                "readonly": self.readonly,
                "logging": self.logging.copy(),
            }
            with conf_path.open('w') as f:
                json.dump(defaults, f, indent=2)
        try:
            with conf_path.open() as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {conf_path}: {e}")
            sys.exit(1)
        # Validate keys
        allowed_keys = {"plugin_registry", "tls_cert", "tls_key", "secure_cookies", "readonly", "logging"}
        for key in data:
            if key not in allowed_keys:
                logger.error(f"Unknown key in {conf_path}: {key}")
                sys.exit(1)
        # Validate types
        if "plugin_registry" in data:
            if not isinstance(data["plugin_registry"], dict):
                logger.error("plugin_registry must be a dict")
                sys.exit(1)
            for ext, path in data["plugin_registry"].items():
                if not isinstance(ext, str) or not isinstance(path, str):
                    logger.error("plugin_registry values must be str: str")
                    sys.exit(1)
        if "tls_cert" in data and data["tls_cert"] is not None:
            if not isinstance(data["tls_cert"], str):
                logger.error("tls_cert must be str or null")
                sys.exit(1)
        if "tls_key" in data and data["tls_key"] is not None:
            if not isinstance(data["tls_key"], str):
                logger.error("tls_key must be str or null")
                sys.exit(1)
        if "secure_cookies" in data:
            if not isinstance(data["secure_cookies"], bool):
                logger.error("secure_cookies must be bool")
                sys.exit(1)
        if "readonly" in data:
            if not isinstance(data["readonly"], bool):
                logger.error("readonly must be bool")
                sys.exit(1)
        if "logging" in data:
            if not isinstance(data["logging"], dict):
                logger.error("logging must be a dict")
                sys.exit(1)
        # Merge
        if "plugin_registry" in data:
            self.plugin_registry.update(data["plugin_registry"])
        if "tls_cert" in data and data["tls_cert"]:
            self.tls_cert = Path(data["tls_cert"])
        if "tls_key" in data and data["tls_key"]:
            self.tls_key = Path(data["tls_key"])
        if "secure_cookies" in data:
            self.secure_cookies = data["secure_cookies"]
        if "readonly" in data:
            self.readonly = data["readonly"]
        if "logging" in data:
            self.logging.update(data["logging"])
