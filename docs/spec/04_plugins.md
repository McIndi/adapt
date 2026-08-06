# Adapt Specification: Plugin System

> **Status:** This document describes the current implementation. The running
> code on `main` wins if it differs. See the
> [documentation contract](../documentation-contract.md) and [user manual](../manual/index.md).

## 1. Plugin selection

`AdaptConfig.plugin_registry` maps file extensions to plugin classes. Discovery
uses this mapping to select a candidate class. It creates the plugin and calls
`detect(path)`. A `False` result rejects the file before `load(path)` runs.

The built-in plugin categories are:

* Dataset plugins for CSV, Excel, and Parquet
* A Python handler plugin for custom FastAPI routers
* HTML and Markdown content plugins
* A generic file plugin for registered document and image types
* A media plugin for audio and video files

The default generic file extensions are `.txt`, `.pdf`, `.json`, `.xml`,
`.svg`, `.png`, `.jpg`, `.jpeg`, `.gif`, and `.webp`. The default media
extensions are `.mp4`, `.mp3`, `.avi`, `.mkv`, `.webm`, `.ogg`, and `.wav`.

The Excel plugin accepts `.xlsx` and `.xls` files. It exposes one resource for
each sheet. Legacy `.xls` resources are read-only.

## 2. Interface

```python
class Plugin:
    def detect(self, path: Path) -> bool: ...
    def load(self, path: Path) -> ResourceDescriptor | Sequence[ResourceDescriptor]: ...
    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]: ...
    def read(self, resource: ResourceDescriptor, request: Request) -> Any: ...
    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any: ...
    def apply_options(self, descriptor: ResourceDescriptor) -> None: ...
    def get_route_configs(self, descriptor: ResourceDescriptor) -> list[tuple[str, APIRouter]]: ...
    def index(self, resource: ResourceDescriptor) -> Iterable[SearchDocument]: ...
    def filter_for_user(self, resource: ResourceDescriptor, user: Any, rows: Iterable[Any]) -> Iterable[Any]: ...
    def default_ui(self, descriptor: ResourceDescriptor) -> str: ...
    def generate_companion_files(self, descriptor: ResourceDescriptor) -> None: ...
```

`ResourceDescriptor` contains `path`, `resource_type`, `schema_path`,
`ui_path`, `options_path`, and `metadata`.

## 3. Method behavior

`detect()` decides whether the candidate plugin accepts a file. The registry
must contain the file extension before discovery calls this method.

`load()` returns one descriptor or a sequence of descriptors. The Excel plugin
returns one descriptor for each sheet.

`schema()` returns schema metadata when the resource has a schema. `read()`
returns the value needed by the plugin route. `write()` handles supported
mutations. Content, generic file, media, and Python plugins reject writes.

`apply_options()` receives parsed companion options after `load()`. Discovery
calls it before companion generation. The base method makes no changes.

`get_route_configs()` returns `(prefix, router)` pairs. Adapt mounts each pair
under extensionless and extension-qualified namespaces. For example,
`records.csv` uses `records` and `records.csv`. The `Sheet1` resource in
`records.xlsx` uses `records/Sheet1` and `records.xlsx/Sheet1`.

`index()` supplies documents to the shared full-text search index. The base
method returns no documents.

`filter_for_user()` is a read extension point for dataset rows. The base method
returns all rows. Built-in plugins do not override it. The shared write path
does not safely enforce write-level row security.

Dataset plugins use `ui_path` for `*.index.html` templates. The media plugin
uses `ui_path` for JSON metadata. Schema files affect serialization and UI
metadata. The shared dataset mutation path also validates supplied create and
update fields against supported schema types before it acquires the resource
lock.

CSV, XLSX, and Parquet mutations use the shared dataset write method and a
resource lock. Each writable plugin uses the shared atomic-write helper.
Legacy `.xls` mutations return `405`.
