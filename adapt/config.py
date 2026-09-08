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


def default_oidc_config() -> dict[str, Any]:
    """Return default OIDC settings. Enable only when issuer and client_id are set."""
    return {
        "issuer": "",
        "client_id": "",
        "client_secret": "",
        "public_url": "",
        "audience": "",
        "username_claim": "preferred_username",
        "groups_claim": "groups",
        "superuser_roles": ["adapt-admin"],
        "local_login": True,
        "scopes": "openid profile",
    }


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
    search_on_startup: bool = True  # Whether to refresh the search index on startup
    mcp_enabled: bool = True  # Whether to mount the MCP server at /mcp
    upload: dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "max_size_bytes": 10 * 1024 * 1024,
        "allowed_extensions": [],
        "denied_extensions": [],
        "strict_mime_sniffing": False,
        "allowed_mime_types": [],
        "collision_policy": "overwrite",
    })
    oidc: dict[str, Any] = field(default_factory=default_oidc_config)
    plugin_registry: dict[str, str] = field(default_factory=lambda: {
        ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
        ".xlsx": "adapt.plugins.excel_plugin.ExcelPlugin",
        ".xls": "adapt.plugins.excel_plugin.ExcelPlugin",
        ".parquet": "adapt.plugins.parquet_plugin.ParquetPlugin",
        ".py": "adapt.plugins.python_plugin.PythonHandlerPlugin",
        ".html": "adapt.plugins.html_plugin.HtmlPlugin",
        ".txt": "adapt.plugins.file_plugin.FilePlugin",
        ".pdf": "adapt.plugins.file_plugin.FilePlugin",
        ".json": "adapt.plugins.file_plugin.FilePlugin",
        ".xml": "adapt.plugins.file_plugin.FilePlugin",
        ".svg": "adapt.plugins.file_plugin.FilePlugin",
        ".png": "adapt.plugins.file_plugin.FilePlugin",
        ".jpg": "adapt.plugins.file_plugin.FilePlugin",
        ".jpeg": "adapt.plugins.file_plugin.FilePlugin",
        ".gif": "adapt.plugins.file_plugin.FilePlugin",
        ".webp": "adapt.plugins.file_plugin.FilePlugin",
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

    def oidc_enabled(self) -> bool:
        """Return True when Keycloak OIDC is configured (issuer and client_id)."""
        issuer = str(self.oidc.get("issuer") or "").strip()
        client_id = str(self.oidc.get("client_id") or "").strip()
        return bool(issuer and client_id)

    def oidc_audience(self) -> str:
        """JWT audience to accept. Defaults to public_url when audience is empty."""
        audience = str(self.oidc.get("audience") or "").strip()
        if audience:
            return audience
        return str(self.oidc.get("public_url") or "").rstrip("/")

    def oidc_public_url(self) -> str:
        return str(self.oidc.get("public_url") or "").rstrip("/")

    def oidc_issuer(self) -> str:
        return str(self.oidc.get("issuer") or "").rstrip("/")

    def local_login_enabled(self) -> bool:
        if not self.oidc_enabled():
            return True
        return bool(self.oidc.get("local_login", True))

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
            "search_on_startup": self.search_on_startup,
            "readonly": self.readonly,
            "debug": self.debug,
            "mcp_enabled": self.mcp_enabled,
            "upload": self.upload.copy(),
            "oidc": {k: v for k, v in self.oidc.items() if k != "client_secret"},
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
            "secure_cookies", "search_on_startup", "readonly", "debug", "logging",
            "mcp_enabled", "upload", "oidc",
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
        for bool_key in ("secure_cookies", "search_on_startup", "readonly", "debug", "mcp_enabled"):
            if bool_key in data and not isinstance(data[bool_key], bool):
                logger.error("%s must be bool", bool_key)
                sys.exit(1)
        if "logging" in data and not isinstance(data["logging"], dict):
            logger.error("logging must be a dict")
            sys.exit(1)
        if "upload" in data:
            if not isinstance(data["upload"], dict):
                logger.error("upload must be a dict")
                sys.exit(1)
            upload = data["upload"]
            if "enabled" in upload and not isinstance(upload["enabled"], bool):
                logger.error("upload.enabled must be bool")
                sys.exit(1)
            if "max_size_bytes" in upload:
                if not isinstance(upload["max_size_bytes"], int):
                    logger.error("upload.max_size_bytes must be int")
                    sys.exit(1)
                if upload["max_size_bytes"] < 1:
                    logger.error("upload.max_size_bytes must be positive")
                    sys.exit(1)
            if "strict_mime_sniffing" in upload and not isinstance(upload["strict_mime_sniffing"], bool):
                logger.error("upload.strict_mime_sniffing must be bool")
                sys.exit(1)
            for list_key in ("allowed_extensions", "denied_extensions"):
                if list_key in upload:
                    if not isinstance(upload[list_key], list) or not all(isinstance(item, str) for item in upload[list_key]):
                        logger.error("upload.%s must be a list of strings", list_key)
                        sys.exit(1)
            if "allowed_mime_types" in upload:
                if not isinstance(upload["allowed_mime_types"], list) or not all(isinstance(item, str) for item in upload["allowed_mime_types"]):
                    logger.error("upload.allowed_mime_types must be a list of strings")
                    sys.exit(1)
            if "collision_policy" in upload:
                if upload["collision_policy"] not in {"overwrite", "reject"}:
                    logger.error("upload.collision_policy must be 'overwrite' or 'reject'")
                    sys.exit(1)
        if "oidc" in data:
            if not isinstance(data["oidc"], dict):
                logger.error("oidc must be a dict")
                sys.exit(1)
            if "client_secret" in data["oidc"]:
                logger.error("oidc.client_secret must not be stored in conf.json; use ADAPT_OIDC_CLIENT_SECRET")
                sys.exit(1)
            allowed_oidc = {
                "issuer", "client_id", "public_url", "audience",
                "username_claim", "groups_claim", "superuser_roles",
                "local_login", "scopes",
            }
            oidc = data["oidc"]
            for key in oidc:
                if key not in allowed_oidc:
                    logger.error("Unknown oidc key in %s: %s", conf_path, key)
                    sys.exit(1)
            for str_key in ("issuer", "client_id", "public_url", "audience", "username_claim", "groups_claim", "scopes"):
                if str_key in oidc and not isinstance(oidc[str_key], str):
                    logger.error("oidc.%s must be str", str_key)
                    sys.exit(1)
            if "local_login" in oidc and not isinstance(oidc["local_login"], bool):
                logger.error("oidc.local_login must be bool")
                sys.exit(1)
            if "superuser_roles" in oidc:
                roles = oidc["superuser_roles"]
                if not isinstance(roles, list) or not all(isinstance(item, str) for item in roles):
                    logger.error("oidc.superuser_roles must be a list of strings")
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
        if "search_on_startup" in data:
            self.search_on_startup = data["search_on_startup"]
        if "readonly" in data:
            self.readonly = data["readonly"]
        if "debug" in data:
            self.debug = data["debug"]
        if "mcp_enabled" in data:
            self.mcp_enabled = data["mcp_enabled"]
        if "upload" in data:
            self.upload.update(data["upload"])
        if "oidc" in data:
            self.oidc.update(data["oidc"])
        if "logging" in data:
            self.logging.update(data["logging"])

    @staticmethod
    def _parse_env_list(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

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
        if "ADAPT_MCP_ENABLED" in os.environ:
            self.mcp_enabled = self._parse_env_bool(os.environ["ADAPT_MCP_ENABLED"], "ADAPT_MCP_ENABLED")
        if "ADAPT_UPLOAD_ENABLED" in os.environ:
            self.upload["enabled"] = self._parse_env_bool(os.environ["ADAPT_UPLOAD_ENABLED"], "ADAPT_UPLOAD_ENABLED")
        if "ADAPT_UPLOAD_MAX_SIZE_BYTES" in os.environ:
            try:
                max_size = int(os.environ["ADAPT_UPLOAD_MAX_SIZE_BYTES"])
            except ValueError:
                logger.error("ADAPT_UPLOAD_MAX_SIZE_BYTES must be an integer")
                sys.exit(1)
            if max_size < 1:
                logger.error("ADAPT_UPLOAD_MAX_SIZE_BYTES must be positive")
                sys.exit(1)
            self.upload["max_size_bytes"] = max_size
        if "ADAPT_UPLOAD_ALLOWED_EXTENSIONS" in os.environ:
            self.upload["allowed_extensions"] = self._parse_env_list(os.environ["ADAPT_UPLOAD_ALLOWED_EXTENSIONS"])
        if "ADAPT_UPLOAD_DENIED_EXTENSIONS" in os.environ:
            self.upload["denied_extensions"] = self._parse_env_list(os.environ["ADAPT_UPLOAD_DENIED_EXTENSIONS"])
        if "ADAPT_UPLOAD_STRICT_MIME_SNIFFING" in os.environ:
            self.upload["strict_mime_sniffing"] = self._parse_env_bool(
                os.environ["ADAPT_UPLOAD_STRICT_MIME_SNIFFING"],
                "ADAPT_UPLOAD_STRICT_MIME_SNIFFING",
            )
        if "ADAPT_UPLOAD_ALLOWED_MIME_TYPES" in os.environ:
            self.upload["allowed_mime_types"] = self._parse_env_list(os.environ["ADAPT_UPLOAD_ALLOWED_MIME_TYPES"])
        if "ADAPT_UPLOAD_COLLISION_POLICY" in os.environ:
            policy = os.environ["ADAPT_UPLOAD_COLLISION_POLICY"].strip().lower()
            if policy not in {"overwrite", "reject"}:
                logger.error("ADAPT_UPLOAD_COLLISION_POLICY must be 'overwrite' or 'reject'")
                sys.exit(1)
            self.upload["collision_policy"] = policy
        if "ADAPT_OIDC_ISSUER" in os.environ:
            self.oidc["issuer"] = os.environ["ADAPT_OIDC_ISSUER"].strip()
        if "ADAPT_OIDC_CLIENT_ID" in os.environ:
            self.oidc["client_id"] = os.environ["ADAPT_OIDC_CLIENT_ID"].strip()
        if "ADAPT_OIDC_CLIENT_SECRET" in os.environ:
            self.oidc["client_secret"] = os.environ["ADAPT_OIDC_CLIENT_SECRET"]
        if "ADAPT_OIDC_PUBLIC_URL" in os.environ:
            self.oidc["public_url"] = os.environ["ADAPT_OIDC_PUBLIC_URL"].strip()
        if "ADAPT_OIDC_AUDIENCE" in os.environ:
            self.oidc["audience"] = os.environ["ADAPT_OIDC_AUDIENCE"].strip()
        if "ADAPT_OIDC_USERNAME_CLAIM" in os.environ:
            self.oidc["username_claim"] = os.environ["ADAPT_OIDC_USERNAME_CLAIM"].strip()
        if "ADAPT_OIDC_GROUPS_CLAIM" in os.environ:
            self.oidc["groups_claim"] = os.environ["ADAPT_OIDC_GROUPS_CLAIM"].strip()
        if "ADAPT_OIDC_SUPERUSER_ROLES" in os.environ:
            self.oidc["superuser_roles"] = self._parse_env_list(os.environ["ADAPT_OIDC_SUPERUSER_ROLES"])
        if "ADAPT_OIDC_LOCAL_LOGIN" in os.environ:
            self.oidc["local_login"] = self._parse_env_bool(
                os.environ["ADAPT_OIDC_LOCAL_LOGIN"], "ADAPT_OIDC_LOCAL_LOGIN"
            )
        if "ADAPT_OIDC_SCOPES" in os.environ:
            self.oidc["scopes"] = os.environ["ADAPT_OIDC_SCOPES"].strip()
