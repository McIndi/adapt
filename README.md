# Adapt — The Adaptive File-Backed Web Server

Adapt is a lightweight, FastAPI-powered adaptive server that automatically turns files and Python modules into fully functional REST APIs.
Drop a CSV, Excel file, Markdown document, HTML page, Parquet-style dataset, or Python handler into a directory and Adapt instantly generates:

* CRUD API endpoints
* HTML DataTables UI (sortable, searchable)
* Inline editing with PATCH support
* Automatic schema inspection
* Safe writes via file locking
* Plugin-driven handlers
* Authentication, users, groups, and permissions
* Admin dashboard for managing users, groups, locks, and caches

A backend that lives in a folder.

---

## Features

### Adaptive File Discovery

On startup, Adapt:

* Scans the document root
* Detects supported files & handlers
* Builds REST routes
* Generates HTML table UIs for CSV/XLSX
* Loads schema overrides and custom renderers
* Registers Python handlers automatically
* Serves HTML and Markdown files directly at extensionless URLs
* Creates companion files in a hidden `.adapt` directory to avoid cluttering the docroot

No configuration required.

---

## Automatic CRUD API

For CSV, Excel sheets, and Parquet-like datasets, Adapt exposes:

* `GET` — read items
* `POST` — create/append items
* `PATCH` — modify items
* `DELETE` — remove items
* `/schema` — view or override JSON schema

Each Excel **sheet** receives its own resource, enabling full CRUD operations per sheet. This multi-sheet support was recently enhanced to make the ExcelPlugin fully compatible with the DatasetPlugin architecture, allowing each sheet to be treated as an independent dataset with its own API endpoints and UI.

The plugin system is extensible, allowing any plugin to create sub-resources by setting a "sub_namespace" in the resource metadata, enabling hierarchical API routes for complex file formats.

---

## Built-In HTML UIs (DataTables)

CSV and Excel datasets automatically generate a full-featured HTML UI:

* Sortable columns
* Search box
* Pagination
* Column hiding
* Responsive layout
* Automatic schema-based type formatting
* Inline editing (PATCH)
* Form-based row addition (POST)
* Row deletion (DELETE)
* **Common navigation bar** with links to API docs, admin dashboard (for superusers), dropdown of all discovered datasets, and logout

This UI is powered by DataTables and delivered entirely over static routes — no framework or build step required.

Perfect for:

* Internal dashboards
* Quick data exploration
* Lightweight admin interfaces
* Local-first tools

---

## Python Handler Plugins (`*.py`)

Drop Python files into your doc root to auto-register custom FastAPI routes.

If the file defines an `APIRouter` named `router`:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/hello")
def hello():
    return {"message": "Hello from a file handler!"}
```

Adapt mounts it under:

```
/api/<filename>/*
```

This enables:

* Custom business logic
* Aggregation endpoints
* Integrations with external APIs
* Data transformations
* Secured/role-based logic layers

Without editing the core server.

---

## Safe Write Operations

Writes to CSV, Excel, and Parquet-like files follow a strict, atomic workflow:

1. Permission check
2. Acquire a file lock (with unique constraint to prevent race conditions)
3. Write to a temporary file
4. Atomic rename/move
5. Release lock

**Lock Safety Features:**
* Database-level unique constraint prevents concurrent lock acquisition
* Automatic retry with exponential backoff (30-second timeout)
* Stale lock cleanup on server startup (5-minute threshold)
* Lock expiration (5-minute TTL by default)

Prevents corruption during concurrent writes and ensures automatic recovery from crashes.

---

## Authentication & Authorization

Adapt includes a complete security layer for multi-user deployments:

### Session-Based Authentication

* Cookie-based login system (HttpOnly, Secure, SameSite flags for comprehensive protection)
* PBKDF2 password hashing with per-user salts (100,000 iterations)
* 7-day session expiration with **active enforcement** and automatic cleanup
* Sliding session renewal - active sessions stay valid
* Background task removes expired sessions (runs daily)
* Timing attack mitigation with constant-time operations
* Automatic redirect to login for unauthenticated browser requests
* JSON error responses for API clients

### User Management

* Create and manage users via Admin UI or CLI
* Superuser role for administrative access
* Active/inactive user status
* Secure password storage (never plaintext)

### Group-Based Permissions

* Organize users into groups (teams, departments, roles)
* Assign permissions to groups, not individual users
* Users inherit permissions from all their groups
* Supports complex organizational hierarchies

### Resource-Level Permissions

* Granular control over dataset access
* Two permission types: `read` and `write`
* Permissions map to resource namespaces (e.g., `data`, `workbook/People`)
* Automatic enforcement on all dynamically generated routes
* Superusers bypass all permission checks

### Permission Enforcement

All dataset routes (`/api/*`, `/ui/*`, `/schema/*`) are automatically protected:

1. User must be authenticated (valid session cookie)
2. User must have appropriate permission for the resource
3. GET requests require `read` permission
4. POST/PUT/PATCH/DELETE require `write` permission
5. 403 Forbidden if permission denied

---

## Admin UI

Adapt ships with a built-in admin interface at `/admin/` to manage the entire security layer:

### Users Tab

* Create new users with username and password
* Set superuser status
* Delete users
* View all registered users

### Groups Tab

* Create groups with names and descriptions
* Manage group membership (add/remove users)
* Assign permissions to groups
* Delete groups

### Permissions Tab

* Define new permissions (resource + action pairs)
* View all available permissions
* Delete unused permissions
* Assign permissions to groups

### Locks Tab

* View current file locks
* Release stale locks
* Monitor concurrent access

The Admin UI uses vanilla HTML/CSS/JavaScript for portability and simplicity—no build step required.

---

## Custom Overrides

Optional companion files customize behavior:

| File                                | Purpose                     |
| ----------------------------------- | --------------------------- |
| `.adapt/dataset.schema.json`        | Override inferred schema    |
| `.adapt/dataset.index.html`         | Custom HTML view            |
| `.adapt/dataset.write.py`           | Override write logic        |
| `.adapt/dataset.<sheet>.html`       | Sheet-level HTML override   |
| `.adapt/dataset.<sheet>.schema.json`| Sheet-level schema override |

---

## Plugin Registry & Companion Files

`AdaptConfig` embeds a `plugin_registry` that maps file extensions to dotted paths for the classes that own those datasets. The default registry wires `.csv`, `.xlsx`, and `.parquet` files to the built-in dataset plugins, but you can override the mapping to point at your own loaders. Each plugin is responsible for producing the inferred JSON schema that becomes the companion `.adapt/*.schema.json`. Those companion files are generated once on server startup and never exposed directly over HTTP—they exist purely to inform the API responses, HTML UI rendering, and validation layers.

Plugins now have full control over route generation via the `get_route_configs` method. This allows plugins to define their own API, Schema, and UI endpoints, including injecting necessary context (like `api_url`) into UI templates. This architecture supports complex multi-resource files (like Excel workbooks) by allowing plugins to generate hierarchical routes using "sub_namespace" metadata.

### Stability & Testing

The plugin system is backed by a strict interface contract (`adapt.plugins.base.Plugin`) and a comprehensive test suite. This ensures that custom plugins—whether for new file types or complex logic—integrate seamlessly with the core discovery and routing engines. The `ResourceDescriptor` acts as the immutable boundary between the file system and your code.

## CLI Commands

The `adapt` CLI includes a few core commands:

* `adapt serve <root>` — serve the given document root (supports `--host`, `--port`, `--tls-cert`, `--tls-key`, `--reload`, `--readonly`).
* `adapt check <root>` — sanity-check the configuration, initialize `.adapt.db`, and print the discovered datasets.
* `adapt addsuperuser --username <name>` — create a local superuser backed by `.adapt.db`.
* `adapt list-endpoints <root>` — show the automatically generated `/api/*`, `/ui/*`, and `/schema/*` paths for every resource.

## Installation

```
pip install adapt-server
```

Serve your directory:

```
adapt serve ./data
```

Runs on Uvicorn with TLS, RBAC, caching, locking, and adaptive routing.

---

## Example Directory Layout

```
data/
  employees.csv
  employees.schema.json
  sales.xlsx
  sales.q1.html
  stats.py
  readme.md
  index.html
  docs/
    guide.md
```

Adapt exposes:

* `/ui/employees` — DataTables UI
* `/api/employees` — CRUD API
* `/api/sales` — sheet listing
* `/api/sales/<sheet>` — CRUD API for each sheet
* `/api/stats/*` — handler routes
* `/readme` — rendered Markdown content
* `/index` — HTML page content
* `/docs/guide` — rendered Markdown content
* `/admin/*` — admin UI

---

## Roadmap

* Visual schema editor
* File watchers (hot-reload route generation)
* SQL access layer (virtual SQLite tables)
* S3 / cloud-backed storage providers
* Multi-tenant mode
* GraphQL auto-introspection
* Audit log browser in Admin UI
* Plugin marketplace

---

## License

TBD: Open-source core + commercial enterprise plugins/support.

---

# Adapt

Your filesystem is now an API platform.

