# Plugin Development

[Previous](configuration) | [Next](architecture) | [Index](index)

This guide describes the plugin APIs that are currently implemented in Adapt.

## Core Plugin Interfaces

Adapt plugin interfaces live in `adapt/plugins/base.py`.

### `PluginContext`

`PluginContext` provides shared execution context:

- `engine`
- `root`
- `readonly`
- `lock_manager`

### `ResourceDescriptor`

A discovered resource is represented by:

- `path`
- `resource_type`
- `schema_path`
- `ui_path`
- `metadata`

### `Plugin` Base Class

A plugin must implement:

- `detect(path)`
- `load(path)`
- `schema(resource)`
- `read(resource, request)`
- `write(resource, data, request, context)`

Optional extension points:

- `get_route_configs(descriptor)`
- `filter_for_user(resource, user, rows)`
- `default_ui(descriptor)`
- `generate_companion_files(descriptor)`

## How Discovery Works

Discovery scans docroot and selects plugins by file extension via `plugin_registry`.

Important behavior:

- Extension mapping is authoritative.
- `detect()` remains part of the plugin contract, but discovery currently selects plugin classes from extension mapping first.

## Plugin Registration

Configure plugins in `DOCROOT/.adapt/conf.json` under `plugin_registry`.

Use dotted class paths (not `module:Class`):

```json
{
  "plugin_registry": {
    ".csv": "adapt.plugins.csv_plugin.CsvPlugin",
    ".myext": "my_plugin.plugin.MyPlugin"
  }
}
```

## Route Mounting Model

Plugins return route configs as `(prefix, router)` pairs.

Generated mounting combines prefix and namespace into routes such as:

- `/api/<namespace>`
- `/schema/<namespace>`
- `/ui/<namespace>`
- `/media/<namespace>`

For each resource, Adapt mounts routes for both extensionless and extension-qualified namespaces where applicable.

## Implementing a Dataset-Style Plugin

Dataset-style plugins can inherit from `DatasetPlugin` to reuse schema/UI/mutation patterns.

Expected mutation contract:

- `POST /api/<resource>` with `{ "action": "create", "data": [...] }`
- `PATCH /api/<resource>` with `{ "action": "update", "data": { ... } }`
- `DELETE /api/<resource>` with `{ "action": "delete", "data": { ... } }`

Mutations should:

- Respect `context.readonly`
- Use `lock_manager` to avoid unsafe concurrent writes
- Invalidate cache after successful changes

## Example Skeleton

```python
from pathlib import Path
from typing import Any
from fastapi import Request

from adapt.plugins.base import Plugin, ResourceDescriptor, PluginContext


class MyPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".myext"

    def load(self, path: Path) -> ResourceDescriptor:
        return ResourceDescriptor(path=path, resource_type="myext")

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        return {}

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        return {"ok": True}

    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any:
        if context.readonly:
            raise RuntimeError("read-only mode")
        return {"success": True}
```

## Python Handler Plugins

The built-in Python handler plugin (`.py`) loads modules and mounts an `APIRouter` named `router` under `/api/<filename>`.

If import fails, the handler is skipped.

## Companion Files

Built-in dataset plugins generate companion files under `.adapt/`:

- `*.schema.json`
- `*.index.html`

Media plugins may write metadata-style companion content via `ui_path` handling.

## Testing Recommendations

When creating plugins, test:

- Discovery and load behavior
- Schema generation
- Read/write behavior
- Read-only mode behavior
- Lock conflict behavior
- Route registration and endpoint responses

## Compatibility Notes

- Keep plugin class paths stable for `plugin_registry` users.
- Prefer additive schema changes when possible.
- Document any plugin-specific configuration keys clearly.

[Previous](configuration) | [Next](architecture) | [Index](index)
