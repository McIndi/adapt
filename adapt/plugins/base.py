from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence, TYPE_CHECKING

from fastapi import Request
from fastapi.routing import APIRouter
from sqlalchemy import Engine

if TYPE_CHECKING:
    from ..locks import LockManager


@dataclass
class PluginContext:
    engine: Engine
    root: Path
    readonly: bool
    lock_manager: "LockManager"


@dataclass
class ResourceDescriptor:
    path: Path
    resource_type: str
    schema_path: Path | None = None
    ui_path: Path | None = None
    write_override_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    @abstractmethod
    def detect(self, path: Path) -> bool:
        ...

    @abstractmethod
    def load(self, path: Path) -> ResourceDescriptor | Sequence[ResourceDescriptor]:
        ...

    @abstractmethod
    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        """Return template name and context for UI rendering."""
        return "", {}

    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]:
        """Return list of (prefix, router) tuples for mounting routes."""
        return []

    def filter_for_user(self, resource: ResourceDescriptor, user: Any, rows: Iterable[Any]) -> Iterable[Any]:
        """Filter rows based on user context (Row-Level Security).
        
        Default implementation returns all rows. Override this in plugins to implement RLS.
        """
        return rows

    def default_ui(self, descriptor: ResourceDescriptor) -> str:
        return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{descriptor.path.stem} Data Preview</title>
</head>
<body>
  <h1>{descriptor.path.stem}</h1>
  <p>DataTables UI will be generated dynamically by Adapt.</p>
</body>
</html>
""".strip()

    def default_write_override(self, descriptor: ResourceDescriptor) -> str:
        return """from adapt.plugins import PluginContext

def write(context: PluginContext, resource, data, request):
    return context.default_write(resource, data, request)
"""

    def generate_companion_files(self, descriptor: ResourceDescriptor) -> None:
        """Generate companion files for the resource.
        
        Default implementation does nothing. Override in plugins that need companion files.
        """
        pass


def discover_plugins(root: Path) -> Iterable[Plugin]:
    """Discover plugin definitions in the document root.

    This placeholder simply yields an empty list; concrete implementations
    should iterate `root.glob(\"*.py\")`, detect routers, and return plugin
    instances.
    """
    return []


def ensure_file(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")