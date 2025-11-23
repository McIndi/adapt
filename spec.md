# **Adapt Specification (v0.2)**

*A Local-First Adaptive File-Backed Web Server*

---

# **1. Overview**

Adapt is an adaptive, local-first backend server built on FastAPI. It automatically exposes files and Python modules as REST endpoints and interactive HTML UIs.

Place files into a directory, and Adapt generates:

* REST CRUD APIs
* HTML DataTables interfaces with sorting, searching, and pagination
* Inline editing (PATCH) with schema-aware validation
* Safe writes (locking + atomic replacement)
* Automatic schema generation and override scaffolding
* Auto-registered FastAPI routers from Python files
* Users, groups, and RBAC
* Admin UI for managing users, groups, permissions, locks, and cache

Adapt treats your filesystem as a structured backend environment. Companion files (schemas, UIs, overrides) are stored in a hidden `.adapt` directory to keep the docroot clean.

---

# **2. Goals and Principles**

### **Goals**

* Provide instant backends for file-based datasets
* Deliver high-quality UIs without build tools
* Support rapid custom logic with Python handler files
* Maintain strict safety (locking, schemas, permissions)
* Follow local-first, privacy-centric principles
* Enable extensibility via plugins

### **Non-Goals**

* Not a replacement for relational DBs
* Not intended for high-throughput, real-time apps

---

# **3. Architecture**

Adapt includes the following major subsystems:

* File Discovery Engine
* Companion File Generator
* Plugin System
* Dynamic Route Generator
* Dataset Engine (CSV/XLSX/Parquet)
* HTML UI Renderer
* Python Handler Loader
* Schema Engine
* Locking + Atomic Writer
* RBAC System (Authentication, Users, Groups, Permissions)
* Admin UI
* CLI + Config System

---

# **4. Authentication and Authorization System**

### **Purpose**

Provide secure, multi-user access control for all Adapt resources.

### **Architecture**

The RBAC (Role-Based Access Control) system consists of four main components:

1. **Authentication Layer** - Session-based login with cookie storage
2. **User & Group Management** - Organize users into groups for permission inheritance
3. **Permission System** - Resource-level permissions (read/write) assigned to groups
4. **Enforcement Layer** - Automatic permission checking on all routes

### **Database Schema**

```sql
-- Users table
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE
);

-- Groups table
CREATE TABLE "group" (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

-- User-Group membership (many-to-many)
CREATE TABLE usergroup (
    user_id INTEGER REFERENCES user(id),
    group_id INTEGER REFERENCES "group"(id),
    PRIMARY KEY (user_id, group_id)
);

-- Permissions table
CREATE TABLE permission (
    id INTEGER PRIMARY KEY,
    resource TEXT NOT NULL,  -- e.g., "data", "workbook/People"
    action TEXT NOT NULL,    -- "read" or "write"
    description TEXT,
    UNIQUE (resource, action)
);

-- Group-Permission assignment (many-to-many)
CREATE TABLE grouppermission (
    group_id INTEGER REFERENCES "group"(id),
    permission_id INTEGER REFERENCES permission(id),
    PRIMARY KEY (group_id, permission_id)
);

-- Session storage
CREATE TABLE session (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES user(id),
    token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    last_active TIMESTAMP NOT NULL
);
```

### **Authentication Flow**

1. User submits credentials to `/auth/login`
2. Server validates username/password (PBKDF2 hash comparison)
3. Server creates session record with random token
4. Server sets HttpOnly cookie with session token
5. Subsequent requests include cookie automatically
6. Middleware validates session and attaches user to request

### **Permission Checking**

For each protected route:

1. Extract user from session cookie
2. Check if user is superuser (bypass all checks)
3. Query database for user's permissions via group membership:
   ```sql
   SELECT permission.*
   FROM permission
   JOIN grouppermission ON grouppermission.permission_id = permission.id
   JOIN usergroup ON usergroup.group_id = grouppermission.group_id
   WHERE usergroup.user_id = ? 
     AND permission.resource = ?
     AND permission.action = ?
   ```
4. Return 403 Forbidden if no matching permission found

### **Automatic Enforcement**

All dynamically generated routes (`/api/*`, `/ui/*`, `/schema/*`) are protected via FastAPI dependency injection:

```python
app.include_router(
    router,
    prefix=full_prefix,
    dependencies=[Depends(permission_dependency("auto", namespace))]
)
```

The `permission_dependency` function:
- Extracts authenticated user from session
- Determines action from HTTP method (GET=read, POST/PUT/PATCH/DELETE=write)
- Checks permission via database query
- Raises HTTPException(403) if denied

### **Admin Endpoints**

The Admin UI is backed by REST endpoints at `/admin/*`:

- `GET/POST /admin/users` - User CRUD
- `GET/POST /admin/groups` - Group CRUD
- `GET/POST/DELETE /admin/permissions` - Permission CRUD
- `POST/DELETE /admin/groups/{id}/members/{user_id}` - Group membership
- `POST/DELETE /admin/groups/{id}/permissions/{perm_id}` - Permission assignment

All admin endpoints require superuser privileges via `Depends(require_superuser)`.

### **Security Features**

- **Password Hashing:** PBKDF2 with 100,000 iterations and per-user salt
- **Session Expiration:** 7-day TTL, automatic cleanup
- **HttpOnly Cookies:** Prevents XSS attacks
- **Constant-Time Comparison:** Prevents timing attacks
- **Secure by Default:** No permission = no access
- **Superuser Bypass:** Emergency access for administrators

---

# **5. File Discovery Engine**

### **Purpose**

Scan the document root and identify all resources to expose.

### **Responsibilities**

* Recursively walk the root directory
* Identify supported file types
* Associate companion files (schema, HTML UI, write overrides)
* Detect Python handler files
* Produce a list of resources to load via plugins

### **Supported File Types**

| Extension  | Handler               |
| ---------- | --------------------- |
| `.csv`     | CSV Plugin            |
| `.xlsx`    | Excel Plugin          |
| `.xls`     | Excel Plugin          |
| `.html`    | HTML Plugin           |
| `.md`      | Markdown Plugin       |
| `.parquet` | Parquet Plugin        |
| `.py`      | Python Handler Plugin |
| `.json`    | Schema/override files |

---

# **5. Companion File Generator (NEW)**

During startup:

### **If a companion file does not exist, Adapt generates it automatically in the `.adapt/` directory.**

This enables users to edit/override defaults easily without cluttering the docroot.

### **Generated Files**

| Type                                       | Default Content                                    |
| ------------------------------------------ | -------------------------------------------------- |
| Schema (`.adapt/*.schema.json`)            | JSON schema inferred from dataset                  |
| HTML UI (`.adapt/*.index.html`, `.adapt/*.<sheet>.html`) | Default DataTables UI template                     |
| Write Override (`.adapt/*.write.py`)       | Stub file that calls plugin’s default write method |

### **Example generated schema**

```json
{
  "type": "object",
  "primary_key": "_row_id",
  "columns": {
    "name": {"type": "string"},
    "age": {"type": "integer"}
  }
}
```

### **Example generated UI (minimal HTML stub)**

Contains:

* DataTables setup
* Inline editing hooks
* Basic template users can customize

### **Example generated write override stub**

```python
# Override this to customize write logic
def write(context, resource, data, request):
    return context.default_write(resource, data, request)
```

---

# **6. Plugin System**

A plugin is a module implementing the following interface:

```python
```python
class Plugin:
    def detect(self, path: Path) -> bool: ...
    def load(self, path: Path) -> ResourceDescriptor | Sequence[ResourceDescriptor]: ...
    def schema(self, resource: ResourceDescriptor) -> dict[str, Any]: ...
    def read(self, resource: ResourceDescriptor, request: Request) -> Any: ...
    def write(self, resource: ResourceDescriptor, data: Any, request: Request, context: PluginContext) -> Any: ...
    def get_route_configs(self, resource: ResourceDescriptor) -> list[tuple[str, APIRouter]]: ...
    def get_ui_template(self, resource: ResourceDescriptor) -> tuple[str, dict[str, Any]]: ...
```
```

Below is the full semantic definition.

### Plugin Registry

Adapt maintains a `plugin_registry` inside the configuration (defaulting to the included dataset plugins) that maps file extensions to dotted paths for the plugin classes responsible for each handler. During discovery, the listed plugin is instantiated, produces the companion schema, and supplies any default UI/write stubs, so overriding the registry lets you swap in new behavior without changing the core server.

### Plugin Types

Adapt supports different types of plugins based on the nature of the content:

* **Dataset Plugins** (CSV, Excel, Parquet): Provide full CRUD APIs, schemas, and DataTables UIs
* **Handler Plugins** (Python): Custom FastAPI routers for business logic
* **Content Plugins** (HTML, Markdown): Serve static content directly at extensionless URLs

Content plugins differ from dataset plugins in that they don't generate API/UI/schema routes, only direct content routes for serving the rendered content.

---

## **6.1 `detect(self, path)`**

### Purpose

Determine whether the plugin owns the file.

### Called

Startup (file discovery)

### Inputs

`path`: full filesystem path

### Returns

`True` or `False`

### Notes

Must be resilient to unreadable/unsupported files.

---

## **6.2 `load(self, path)`**

### Purpose

Create one or more **Resource Objects**, containing all metadata required for the plugin to operate. For files with multiple sub-resources (e.g., Excel sheets), this returns a sequence of ResourceDescriptors.

### Called

Startup, only if `detect()` returns `True`.

### Inputs

`path`: the dataset or handler file

### Returns

A ResourceDescriptor or Sequence[ResourceDescriptor]. The `ResourceDescriptor` is the strict contract passed between the discovery engine and the plugin methods. It contains:

* normalized path
* dataset metadata (columns, sheets, encoding…)
* references to companion files
* plugin state
* identifiers used for auto-route generation
* Optional "sub_namespace" for hierarchical routing

### Notes

Adapt will pass each ResourceDescriptor back into `schema`, `read`, `write`, and `routes`. For multi-resource plugins, each descriptor gets its own routes and companion files.

---

## **6.3 `schema(self, resource)`**

### Purpose

Return the JSON schema for this resource.

### Called

* During startup (for schema endpoints)
* At runtime when `/schema` is requested
* When generating missing `.adapt/*.schema.json` companion files

### Inputs

`resource`: Resource Object

### Returns

JSON-serializable schema dict

### Behavior

* Use companion schema if present
* Otherwise infer schema
* Must never mutate the underlying data file

---

## **6.4 `read(self, resource, request)`**

### Purpose

Return resource data for `GET` operations.

### Called

Runtime on any `GET` route the plugin controls.

### Inputs

* `resource`: Resource Object
* `request`: FastAPI request

### Returns

JSON-serializable response (list, dict, structured object)

### Behavior

* Must not modify data
* May take advantage of Adapt caching (cache managed by Adapt)

---

## **6.5 `write(self, resource, data, request)`**

### Purpose

Handle `POST`, `PATCH`, and `DELETE` operations.

### Called

Runtime, after Adapt:

1. Performs RBAC checks
2. Acquires file lock
3. Loads existing data
4. Provides payload to plugin

### Inputs

* `resource`
* `data`: decoded request body
* `request`

### Returns

JSON serializable result (status or updated rows)

### Required Behavior

* Validate inputs against schema
* Apply modifications
* Write to temporary file
* Adapt performs atomic commit
* Throw structured validation errors if needed

---

---

## **6.6 `get_route_configs(self, resource)`**

### Purpose

Register **all endpoints** generated by the plugin (API, Schema, UI).

### Called

Startup, during route generation.

### Inputs

`resource`: Resource Object

### Returns

List of `(prefix, APIRouter)` tuples.

### Use Cases

* Defining standard CRUD routes
* Defining Schema routes
* Defining UI routes with custom context injection
* Excel sheet listing
* Virtual endpoints
* Aggregations and transformations

---

# **7. Dynamic Route Generator**

### Responsibilities

* Generate CRUD routes for datasets
* Generate `/schema` route for datasets
* Generate HTML UI endpoints for datasets
* Generate direct content routes for HTML/Markdown files
* Mount Python handler routers
* Mount plugin-provided routers
* Build Admin UI routes

Everything is performed based on:

* detected files
* plugin behavior (via `get_route_configs`)
* companion file presence

The Dynamic Route Generator now delegates the creation of specific routes (API, Schema, UI) to the plugins themselves. This allows plugins to have full control over the URL structure and the context provided to their handlers.

---

# **8. Dataset Engine**

Handles structured datasets (CSV, Excel sheets, Parquet-like).

### Responsibilities

* Schema inference
* Row-level CRUD
* Type validation
* Inline editing via PATCH
* Duplicate row ID management
* Write-through with locking
* Companion file generation

### Supported Types

string, number, boolean, datetime, enum

### Excel Behavior

Each sheet becomes a resource via the "sub_namespace" mechanism:

* `/api/file/<sheet>` — CRUD API for each sheet
* `/ui/file/<sheet>` — HTML UI for each sheet
* `/schema/file/<sheet>` — Schema for each sheet

Companion files are generated per sheet: `.adapt/file.<sheet>.schema.json`, `.adapt/file.<sheet>.index.html`, etc.

This design allows the ExcelPlugin to be fully compatible with the DatasetPlugin architecture while handling multi-sheet workbooks.

---

# **9. HTML UI Renderer (DataTables)**

### Features

* Sortable columns
* Global search
* Pagination
* Responsive layout
* Inline editing (PATCH)
* Row add (POST)
* Row delete (DELETE)

### Customization

`.adapt/*.index.html` and `.adapt/*.<sheet>.html` allow full replacement.

### Automatic UI Creation

If no UI file exists, Adapt generates a default DataTables view.

---

# **10. Python Handler Loader**

### Behavior

Any `*.py` file with:

```python
from fastapi import APIRouter
router = APIRouter()
```

…is mounted at `/api/<name>/*`.

### Uses

* business logic
* API composition
* computed endpoints
* authentication layers
* user-defined microservices

---

# **11. Schema Engine**

### Responsibilities

* Infer schema from CSV/XLSX
* Merge schema overrides
* Generate default schema files
* Provide validation error messages

---

# **12. Safe Writes (Locking + Atomic Write System)**

### Guarantees

* One writer at a time
* Writer cannot be interrupted mid-write
* All writes use temp files + atomic move
* Locks recorded and visible in Admin UI
* Stale lock detection

---

# **13. Cache Engine**

### Features

* Automatic cache of GET responses
* Cache invalidation on write
* Cache visibility and clearing via Admin UI

---

# **14. RBAC System**

### Models

* **User**
* **Group**
* **Permission**

### Permissions

* File-level CRUD
* API-level route permissions
* Python handler-level permission rules
* UI access

### Storage

Local JSON DB or pluggable backends.

---

# **15. Admin UI**

### Modules

#### Users

* Create, update, delete
* Change password
* Assign to groups

#### Groups

* Create/delete groups
* Manage membership
* Assign permissions

#### Permissions

* Full permission matrix

#### System

* Active locks
* Force unlock
* Cache viewer
* Clear cache

---

# **16. Companion File Specification**

### Companion Files Generated at Startup if Missing

| File                      | Description                |
| ------------------------- | -------------------------- |
| `.adapt/name.schema.json` | JSON schema for dataset    |
| `.adapt/name.index.html`  | Default HTML DataTables UI |
| `.adapt/name.<sheet>.html`| Default sheet-level UI     |
| `.adapt/name.write.py`    | Stub write override        |

All generated files are safe to edit, version, and override.
Companion files are not served directly. They are generated once on startup (if missing) and used by the API/UI layers to drive schema inference, DataTables rendering, and write hooks without exposing the stub files over HTTP.

---

# **17. CLI**

### `adapt serve <path> [options]`

Options include:

* `--host`
* `--port`
* `--tls-cert`
* `--tls-key`
* `--read-only`
* `--admin`
* `--log-level`

Additional operational commands:

* `adapt check <path>` — initialize `.adapt.db`, migrate schemas, and list discovered datasets.
* `adapt addsuperuser --username <name>` — create or warn if a superuser already exists in the configured SQLite store.
* `adapt list-endpoints <path>` — print every `/api/*`, `/schema/*`, and `/ui/*` path registered during discovery.

---

# **18. Configuration**

### Sources

* Environment variables
* `adapt.json`
* CLI args
* Defaults

Key settings:

* document root
* authentication enable/disable
* allowed plugins
* write mode
* TLS

---

# **19. Logging and Metrics**

### Logging

* JSON structured logs
* Write operations
* Lock events
* Admin actions

### Metrics

Optional Prometheus-like metrics at `/metrics`.

---

# **20. Error Handling**

All errors use a formatted JSON structure:

```json
{
  "error": "ValidationError",
  "message": "Column 'price' must be numeric",
  "location": "row 4, column price"
}
```

---

# **21. Roadmap**

* Live reload (watch filesystem)
* Virtual SQL layer
* GraphQL views
* Multi-tenant mode
* SSO providers
* Audit logs
* Plugin marketplace
* S3 + remote storage backends

---

# **End of Spec v0.2**

---

If you'd like, I can also generate:

* `plugin.md` (developer-facing plugin documentation)
* `schema.md` (JSON schema for companion files)
* An architecture diagram
* UML diagrams for the plugin system
* A flowchart showing startup → discovery → generation → route registration

Just tell me what you want.
