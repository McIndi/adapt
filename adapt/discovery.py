"""adapt.discovery — Resource discovery: scanning the document root for supported files."""
from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AdaptConfig
from .plugins.base import Plugin, ResourceDescriptor


logger = logging.getLogger(__name__)


@dataclass
class DatasetResource:
    """Represents a discovered dataset resource."""
    path: Path
    relative_path: Path
    resource_type: str
    schema_path: Path
    ui_path: Path
    plugin_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


def should_ignore(path: Path) -> bool:
    """Check if a path should be ignored during discovery.

    Args:
        path: The path to check.

    Returns:
        True if the path should be ignored, False otherwise.
    """
    ignored_dir_names = {
        ".adapt",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
    }

    for part in path.parts:
        if part in ignored_dir_names:
            return True
        if part.startswith("."):
            return True

    return False


def discover_resources(root: Path, config: AdaptConfig) -> list[DatasetResource]:
    """Discover dataset resources in the root directory.

    Args:
        root: The root directory to search.
        config: The Adapt configuration.

    Returns:
        A list of discovered DatasetResource objects.
    """
    logger.info(f"Discovering resources in {root}")
    resources: list[DatasetResource] = []
    supported = {ext for ext in config.plugin_registry}
    adapt_dir = root / ".adapt"

    for path in root.rglob("*"):
        if path.is_dir() or should_ignore(path):
            continue

        ext = path.suffix.lower()
        if ext not in supported:
            continue

        logger.debug(f"Processing file: {path}")
        plugin_cls = config.get_plugin_factory(ext)
        plugin: Plugin = plugin_cls()

        loaded = plugin.load(path)
        if isinstance(loaded, ResourceDescriptor):
            descriptors = [loaded]
        else:
            descriptors = loaded

        for descriptor in descriptors:
            sub_namespace = descriptor.metadata.get("sub_namespace", "")
            suffix = f".{sub_namespace}" if sub_namespace else ""
            base_path = adapt_dir / path.relative_to(root)
            schema_path = base_path.with_suffix(f"{suffix}.schema.json")
            ui_path = base_path.with_suffix(f"{suffix}.index.html")

            descriptor.schema_path = schema_path
            descriptor.ui_path = ui_path

            plugin.generate_companion_files(descriptor)

            resource = DatasetResource(
                path=path,
                relative_path=path.relative_to(root),
                resource_type=descriptor.resource_type,
                schema_path=schema_path,
                ui_path=ui_path,
                plugin_name=plugin_cls.__name__,
                metadata=descriptor.metadata,
            )
            resources.append(resource)

    logger.info(f"Discovered {len(resources)} resources")
    return resources


__all__ = [
    "DatasetResource",
    "discover_resources",
]
