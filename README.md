# Adapt — The Adaptive File-Backed Web Server

Adapt is a lightweight, FastAPI-powered adaptive server that automatically turns files and Python modules into fully functional REST APIs.

Note: README vs Implementation
----------------------------------
The `README.md` outlines the intended design and functionality. Some features are partially implemented, still in the roadmap, or only scaffolded in the repository. For a detailed list of known differences between README/spec and the current implementation, see `IMPLEMENTATION_NOTES.md` at the project root.
---
Drop a CSV, Excel file, Markdown document, HTML page, Parquet-style dataset, audio/video file, or Python handler into a directory and Adapt instantly generates:

* CRUD API endpoints
* HTML DataTables UI (sortable, searchable)
* Inline editing with PATCH support
* HTTP streaming for audio/video files
* Media gallery UI with searchable cards
* Automatic schema inspection
* Safe writes via file locking
* Plugin-driven handlers
* Authentication, users, groups, and permissions
* API Keys for programmatic access
* Audit logging for security and compliance
* Row-Level Security (RLS) for granular data access
* Admin dashboard for managing users, groups, locks, caches, and keys

A backend that lives in a folder.

---

## Features

### Adaptive File Discovery

On startup, Adapt:

* Scans the document root
* Detects supported files & handlers
* Builds REST routes
* Generates HTML table UIs for CSV/XLSX
* Generates media players and galleries for audio/video files
* Loads schema overrides and custom renderers
* Registers Python handlers automatically
* Serves all resources at extensionless URLs for cleaner access (e.g., `data.csv` → `/data`)
* Creates companion files in a hidden `.adapt` directory to avoid cluttering the docroot

No configuration required.

---

## Landing Page

Adapt provides a user-friendly landing page at the root URL (`/`) that serves as the entry point for authenticated users:

* **Welcome Message** - Introduction to Adapt and its capabilities
* **Quick Start Guide** - Step-by-step instructions for getting started
* **Accessible Resources** - Dynamic list of datasets, HTML pages, and Markdown documents the user can access based on their permissions
* **Media Gallery** - Browse and stream audio/video files
* **Admin Access** - Direct link to the admin dashboard for superusers

The landing page adapts to the user's authentication status and permissions, showing only resources they are authorized to view. For unauthenticated users, it displays public HTML and Markdown content.

---

## Automatic CRUD API

For CSV, Excel sheets, and Parquet datasets, Adapt exposes:

* `GET` — read items
* `POST` — create/append items
* `PATCH` — modify items
* `DELETE` — remove items
* `/schema` — JSON schema


### Request Format for Dataset Endpoints

**Note:** For dataset resources (CSV, Excel, Parquet), API requests must use an envelope format specifying the action and data. This is required for all POST, PATCH, and DELETE requests.

**Envelope format:**

```json
{
  "action": "create|update|delete",
  "data": [ ... ] // for create, or { ... } for update/delete
}
```

**Examples:**

*Create rows (POST):*
```json
{
  "action": "create",
  "data": [
    {"id": "899", "name": "Unknown"},
    {"id": "900", "name": "Alice"}
  ]
}
```

*Update a row (PATCH):*
```json
{
  "action": "update",
  "data": {"_row_id": 1, "name": "Updated Name"}
}
```

*Delete a row (DELETE):*
```json
{
  "action": "delete",
  "data": {"_row_id": 2}
}
```

This format is required for all dataset plugin endpoints. Future versions may support simpler payloads, but for now, always wrap your data in this envelope.


Each Excel **sheet** and Parquet file receives its own resource, enabling full CRUD operations per dataset. Parquet support is now robust and consistent with other dataset plugins, including atomic writes, schema inference, and safe concurrent editing.

For audio and video files, Adapt provides HTTP streaming endpoints using open standards for efficient playback, along with individual player pages and a searchable media gallery.

The plugin system is extensible, allowing any plugin to create sub-resources by setting a "sub_namespace" in the resource metadata, enabling hierarchical API routes for complex file formats.

---

## Caching System

Adapt now includes a robust, SQLite-backed caching system:

* GET responses for datasets, media metadata, and rendered content are cached for performance.
* Cache is stored in `.adapt.db` and managed per resource.
* Plugins control what is cached and for how long (TTL).
* Cache is automatically invalidated on resource mutation (POST/PATCH/DELETE).
* Admin UI supports cache inspection and manual invalidation.

All major plugins (CSV, Excel, Parquet, HTML, Markdown, Media, Python handler) now support caching where appropriate. Parquet, CSV, Excel plugins use cache for reads and schema inference. Media plugin caches metadata. Python handler plugin does not cache routers (for safety).

All cache expiry logic uses timezone-aware UTC datetimes.

Comprehensive test suite covers all cache logic and plugin integration.

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

This UI is powered by DataTables and delivered via Jinja2 templates that extend a base template for consistent navigation. Companion files (`.adapt/*.index.html`) are generated during startup and can be customized by users to add features like charts, custom styling, or additional JavaScript. Rendering happens during requests to ensure dynamic data is always current.

Perfect for:

* Internal dashboards
* Quick data exploration
* Lightweight admin interfaces
* Local-first tools

---

## Media Gallery

Audio and video files automatically generate a Netflix/YouTube-style gallery UI:

* Card-based layout with file information, metadata, and video thumbnails
* Searchable by filename
* Direct streaming playback
* Responsive design
* Integrated with common navigation bar

Individual media files also have dedicated player pages with HTML5 video/audio elements for focused viewing. Streaming uses HTTP range requests for open-standard, efficient delivery. Metadata such as duration, bitrate, artist, and title are extracted and displayed where available.

Perfect for:

* Media libraries
* Content management
* Personal streaming servers
* Educational resources

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

Writes to CSV, Excel, and Parquet files follow a strict, atomic workflow:

1. Permission check
2. Acquire a file lock (with unique constraint to prevent race conditions)
3. Write to a temporary file
4. Atomic rename/move
5. Release lock

**Lock Safety Features:**
* Database-level unique constraint prevents concurrent lock acquisition
* Automatic retry with exponential backoff (starting at 0.1s, doubling each attempt, capped at 1.0s, 30-second timeout)
* Stale lock cleanup on server startup (5-minute threshold)
* Lock expiration (5-minute TTL by default)


Parquet plugin now uses the same atomic write logic as CSV and Excel plugins, writing to a temporary file and atomically replacing the original, ensuring data integrity and safe concurrent access.

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
* Automatic redirect to login for unauthenticated browser requests, followed by redirect to landing page after successful authentication
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

### API Keys

* Programmatic access for scripts and external tools
* Generate keys via Admin UI or user Profile page with optional expiration (max 1 year)
* Authenticate via `X-API-Key` header
* Secure storage (SHA-256 hashed)
* Users can self-issue API keys for their own account

### Audit Logging

* Records critical system actions for security and compliance
* Logs: Login/Logout, User/Group changes, Permission changes, API Key management
* Viewable and filterable via Admin UI

### Row-Level Security (RLS)

* Plugins can enforce granular access control based on the authenticated user
* `filter_for_user` hook allows plugins to restrict data visibility
* Applied automatically during data retrieval

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

### API Keys Tab

* Generate new API keys for users (admin only)
* Users can self-manage their API keys via Profile page
* Revoke existing keys
* Set expiration dates (max 1 year)

### Audit Logs Tab

* View chronological history of system actions
* Filter by user, action, or resource
* Inspect action details

### Cache Tab

* View all cached entries with key, resource, expiration, and user
* Delete individual cache entries
* Clear all cache entries
* Monitor cache usage and performance

The Admin UI uses vanilla HTML/CSS/JavaScript for portability and simplicity—no build step required.

---

## Custom Overrides

Optional companion files customize behavior:

| File                                | Purpose                     |
| ----------------------------------- | --------------------------- |
| `.adapt/dataset.schema.json`        | Override inferred schema    |
| `.adapt/dataset.index.html`         | Custom Jinja2 HTML template |
| `.adapt/dataset.<sheet>.html`       | Sheet-level HTML override   |
| `.adapt/dataset.<sheet>.schema.json`| Sheet-level schema override |

---

## Configuration

Adapt supports configuration via a `conf.json` file in `DOCROOT/.adapt/`. If the file doesn't exist, it's created with default values on first run.

The configuration allows customizing:

- `plugin_registry`: Map file extensions to plugin classes (e.g., add custom handlers).
- `tls_cert`: Path to TLS certificate file.
- `tls_key`: Path to TLS key file.
- `secure_cookies`: Whether to set secure flags on cookies.
- `logging`: Logging configuration dictionary for Python's dictConfig.

Precedence: CLI arguments > `conf.json` > defaults.

Example `conf.json`:

```json
{
  "plugin_registry": {
    ".custom": "my_plugin.CustomPlugin"
  },
  "tls_cert": "/path/to/cert.pem",
  "tls_key": "/path/to/key.pem",
  "secure_cookies": true,
  "logging": {
    "root": {
      "level": "DEBUG"
    }
  }
}
```

To reset, delete `conf.json` and restart the server.

---

## Plugin Registry & Companion Files


`AdaptConfig` embeds a `plugin_registry` that maps file extensions to dotted paths for the classes that own those datasets. The default registry wires `.csv`, `.xlsx`, and `.parquet` files to the built-in dataset plugins, all of which now use a consistent interface for schema inference, atomic writes, and safe editing. Parquet support is fully integrated and tested. Each plugin is responsible for producing the inferred JSON schema that becomes the companion `.adapt/*.schema.json`. Those companion files are generated once on server startup and never exposed directly over HTTP—they exist purely to inform the API responses, HTML UI rendering, and validation layers.

HTML companion files (`.adapt/*.index.html`) are generated as Jinja2 templates with pre-computed schema data (e.g., column headers) baked in, allowing for efficient rendering while supporting full customization. If a companion HTML file exists, it overrides the default UI template for that resource.

Plugins now have full control over route generation via the `get_route_configs` method. This allows plugins to define their own API, Schema, and UI endpoints, including injecting necessary context (like `api_url`) into UI templates. This architecture supports complex multi-resource files (like Excel workbooks) by allowing plugins to generate hierarchical routes using "sub_namespace" metadata.

### Stability & Testing

The plugin system is backed by a strict interface contract (`adapt.plugins.base.Plugin`) and a comprehensive test suite. This ensures that custom plugins—whether for new file types or complex logic—integrate seamlessly with the core discovery and routing engines. The `ResourceDescriptor` acts as the immutable boundary between the file system and your code.

## CLI Commands

The `adapt` CLI includes a few core commands:

* `adapt serve <root>` — serve the given document root (supports `--host`, `--port`, `--tls-cert`, `--tls-key`, `--reload`, `--readonly`).
* `adapt check <root>` — sanity-check the configuration, initialize `.adapt.db`, and print the discovered datasets.
* `adapt addsuperuser <root> --username <name>` — create a local superuser backed by `.adapt.db`.
* `adapt list-endpoints <root>` — show the automatically generated `/api/*`, `/ui/*`, and `/schema/*` paths for every resource.

### Admin Commands

Adapt includes administrative commands for managing users, groups, and permissions:

* `adapt admin list-resources <root>` — list all discovered resources in the document root, including sub-namespaces for multi-resource files (e.g., Excel sheets).
* `adapt admin create-permissions <root> <resources>...` — create permissions and groups for specified resources (use `__all__` for all resources, including sub-namespaces).
* `adapt admin list-groups <root>` — display all groups with their associated permissions and assigned users.

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
  video.mp4
  audio.mp3
  stats.py
  readme.md
  index.html
  docs/
    guide.md
```

Adapt exposes:

* `/` — landing page with resource overview
* `/ui/employees` — DataTables UI
* `/api/employees` — CRUD API
* `/api/sales` — sheet listing
* `/api/sales/<sheet>` — CRUD API for each sheet
* `/media/video.mp4` — streaming endpoint
* `/ui/video.mp4` — media player page
* `/ui/media` — media gallery
* `/api/stats/*` — handler routes
* `/readme` — rendered Markdown content
* `/index` — HTML page content
* `/docs/guide` — rendered Markdown content
* `/admin/*` — admin UI

---

## Roadmap

* File watchers (hot-reload route generation)
* GraphQL auto-introspection
* Audit log browser in Admin UI (Completed)
* Plugin marketplace

---

## License

TBD: Open-source core + commercial enterprise plugins/support.

---

# Adapt

Your filesystem is now an API platform.
