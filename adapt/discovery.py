from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import AdaptConfig
from .plugins.base import Plugin, ResourceDescriptor


@dataclass
class DatasetResource:
    path: Path
    relative_path: Path
    resource_type: str
    schema_path: Path
    ui_path: Path
    plugin_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


def should_ignore(path: Path) -> bool:
    return path.name.startswith(".") or ".adapt" in path.parts


def ensure_file(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def discover_resources(root: Path, config: AdaptConfig) -> list[DatasetResource]:
    resources: list[DatasetResource] = []
    supported = {ext for ext in config.plugin_registry}
    adapt_dir = root / ".adapt"

    for path in root.rglob("*"):
        if path.is_dir() or should_ignore(path):
            continue

        ext = path.suffix.lower()
        if ext not in supported:
            continue

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

    return resources


__all__ = [
    "DatasetResource",
    "discover_resources",
]
