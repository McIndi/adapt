from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable
import logging

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
