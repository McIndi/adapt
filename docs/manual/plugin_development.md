# Plugin Development

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

A discovered resource has these attributes:

- `path`
- `resource_type`
- `schema_path`
- `ui_path`
- `options_path`
- `metadata`

### `Plugin` Base Class

A plugin must implement:

- `detect(path)`
- `load(path)`
- `schema(resource)`
- `read(resource, request)`
- `write(resource, data, request, context)`

Optional extension points:

- `apply_options(descriptor)`
- `get_route_configs(descriptor)`
- `index(resource)`
- `filter_for_user(resource, user, rows)`
- `default_ui(descriptor)`
- `generate_companion_files(descriptor)`

## How Discovery Works

Discovery scans the document root. The `plugin_registry` entry for the file
extension selects a candidate plugin.

Important behavior:

- Discovery ignores an extension without a registry entry.
- Discovery creates the candidate plugin and calls `detect(path)`.
- If `detect(path)` returns `False`, discovery ignores the file.
- If `detect(path)` returns `True`, discovery calls `load(path)`.

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

For each resource, Adapt mounts routes for both namespace forms. For `reports.myext`,
the API route exists at `/api/reports/` and `/api/reports.myext/`.

Sub-namespaces follow the filename. For the `Summary` sheet in `reports.xlsx`,
the forms are `/api/reports/Summary/` and `/api/reports.xlsx/Summary/`.

## Implementing a Dataset-Style Plugin

Dataset-style plugins can inherit from `DatasetPlugin` to reuse schema, UI, and mutation patterns.

Set `descriptor.metadata["readonly"]` to `True` for a resource that cannot use
the shared mutation path. You can add a user-facing message in
`descriptor.metadata["readonly_reason"]`. The API returns this message with
status `405`, and the default UI hides its edit controls.

Expected mutation contract:

- `POST /api/<resource>` with `{ "action": "create", "data": [...] }`
- `PATCH /api/<resource>` with `{ "action": "update", "data": { ... } }`
- `DELETE /api/<resource>` with `{ "action": "delete", "data": { ... } }`

Mutations must:

- Respect `context.readonly`
- Use `lock_manager` to avoid unsafe concurrent writes
- Invalidate cache after successful changes

The schema returned by `schema()` supplies serialization hints, UI column
metadata, and validation rules for the shared dataset mutation path. Create and
update fields use the common `string`, `integer`, `number`, and `boolean` types
(plus corresponding pandas type names). Adapt normalizes numeric and boolean
strings. Adapt permits blank strings and `null` values. Unknown columns or
incompatible values return `422` before Adapt locks or writes the resource.
Custom schema types without defined validation semantics remain metadata only.

Adapt applies `filter_for_user()` on dataset reads. It is also available as a
row-filtering extension point. The shared mutation implementation does not
provide safe write-level row-security enforcement. It reads and rewrites the
row collection, and row identifiers can diverge after filtering. A plugin
that needs row-level write authorization must implement and test its own
write path instead of using this hook.
See [Known Limitations](known_limitations.md#write-level-row-security).

## Example Skeleton

```python
from pathlib import Path
from typing import Any, Iterable, Sequence

from fastapi import Request
from fastapi.routing import APIRouter

from adapt.plugins.base import (
    Plugin,
    PluginContext,
    ResourceDescriptor,
    SearchDocument,
)


class MyPlugin(Plugin):
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".myext"

    def load(
        self, path: Path
    ) -> ResourceDescriptor | Sequence[ResourceDescriptor]:
        return ResourceDescriptor(path=path, resource_type="myext")

    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]:
        return {}

    def read(self, resource: ResourceDescriptor, request: Request) -> Any:
        return {"ok": True}

    def write(
        self,
        resource: ResourceDescriptor,
        data: Any,
        request: Request,
        context: PluginContext,
    ) -> Any:
        if context.readonly:
            raise RuntimeError("read-only mode")
        return {"success": True}

    def apply_options(self, descriptor: ResourceDescriptor) -> None:
        pass

    def get_route_configs(
        self, descriptor: ResourceDescriptor
    ) -> list[tuple[str, APIRouter]]:
        router = APIRouter()

        @router.get("/")
        def get_resource(request: Request) -> Any:
            return self.read(descriptor, request)

        return [("api", router)]

    def index(
        self, resource: ResourceDescriptor
    ) -> Iterable[SearchDocument]:
        return []
```

Adapt mounts the returned router under both resource namespaces. It also adds
the resource permission dependency to the router.

## Python Handler Plugins

The built-in Python handler plugin (`.py`) loads modules and mounts an `APIRouter` named `router` under `/api/<filename>`.

If import fails, Adapt skips the handler.

## Companion Files

Built-in dataset plugins generate companion files under `.adapt/`:

- `*.schema.json`
- `*.index.html`

The companion UI filename always ends in `.index.html`. For example, the UI
for the `Dashboard` sheet in `report.xlsx` is
`.adapt/report.Dashboard.index.html`.

The media plugin uses `ui_path` differently. It writes JSON metadata to that
path, not an HTML template.

A generated `*.schema.json` carries `"generated_by": "adapt"`. Adapt refreshes such a
file when the resource's shape changes. Adapt leaves any schema without that key alone.
As a result, Adapt never overwrites hand-written schemas. Adapt strips the key before
it serves the schema from `/schema/<resource>`.

### Resource Options

You can also hand-write `*.options.json` alongside the generated files to override how
Adapt parses a resource. The naming matches the other companion files. For the sheet
`Dashboard` in `report.xlsx`, that is `.adapt/report.Dashboard.options.json`.

Supported keys:

| Key | Applies to | Meaning |
| --- | --- | --- |
| `header_row` | `.xlsx`, `.xls` | 1-based row holding the column names. Defaults to `1`. |

When a sheet opens with a title banner instead of column names, use `header_row`.
Without this option, Adapt parses the banner as the header:

```json
{ "header_row": 3 }
```

Adapt ignores rows above the header row on both read and write operations. Adapt logs
an unreadable options file or an invalid value and ignores it. Adapt does not raise an
error. As a result, a typo cannot crash the server.

To consume options, a plugin overrides `apply_options(descriptor)`. Discovery calls this
method after `load()` and before `generate_companion_files()`. `load()` sees only a path,
so it cannot locate the companion directory. Discovery calls `apply_options()` before
`generate_companion_files()`, so a derived schema reflects the options.

## Testing Recommendations

When you create plugins, test the following:

- Discovery and load behavior
- Schema generation
- Read/write behavior
- Read-only mode behavior
- Lock conflict behavior
- Route registration and endpoint responses

## Compatibility Notes

- Keep plugin class paths stable for `plugin_registry` users.
- Prefer additive schema changes when possible.
- Document any plugin-specific configuration keys.

Manual navigation: [Previous: Configuration](configuration.md) | [Index](index.md) | [Next: Architecture](architecture.md)
