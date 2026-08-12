# Architecture

This document describes the current Adapt architecture.

## High-Level Design

Adapt is a FastAPI application that:

1. Loads configuration from `DOCROOT/.adapt/conf.json`
2. Initializes SQLite-backed storage and cache
3. Selects candidate plugins by extension and uses plugin detection to accept resources
4. Generates API/UI/schema/media routes per discovered resource
5. Enforces authentication and authorization through dependencies

## Core Components

### Application Layer

Key responsibilities in `adapt/app.py`:

- app creation and shared state initialization
- middleware registration
- auth/admin router mounting
- dynamic route generation
- health and landing/media-gallery routes

### Discovery and Plugin Layer

Key modules:

- `adapt/discovery.py`
- `adapt/plugins/*`
- `adapt/routes.py`

Flow:

- Discovery scans docroot
- Extension determines plugin class via `plugin_registry`
- Plugin `detect()` accepts or rejects the file
- Plugin `load()` returns one or more resource descriptors
- Discovery assigns schema, UI, and options companion paths
- Plugin `apply_options()` can modify each descriptor
- Plugins can generate companion files under `.adapt/`
- Adapt mounts the route configuration from each plugin into the app

### Data and Security Layer

Key modules:

- `adapt/storage.py` (SQLModel tables and database engine)
- `adapt/auth/*` (sessions, password, dependencies)
- `adapt/security.py` (CSRF and security headers)
- `adapt/locks.py` (lock manager)
- `adapt/cache.py` (SQLite-backed cache)

## Implemented Middleware and Security Flow

Current middleware stack includes:

- Trusted host middleware
- security middleware (CSRF validation and security headers)
- auth middleware (session user hydration)

Request flow for unsafe methods with session authentication:

1. Adapt validates the CSRF token, using the `adapt_csrf` cookie and the `X-CSRF-Token` header
2. Adapt resolves the user from the session or an API key
3. The endpoint dependency makes sure that the user has permission
4. The route handler executes

## Route Generation Model

For each resource, plugins provide `(prefix, router)` pairs.

Routes are mounted with permission dependencies and namespace variants.

Each resource has an extensionless namespace and an extension-qualified
namespace. For example, `data.csv` uses both `data` and `data.csv`. An Excel
sheet adds its sub-namespace to both forms, such as `data/Sheet1` and
`data.xlsx/Sheet1`.

Common prefixes:

- `api`
- `schema`
- `ui`
- `media`

Dataset plugins use `ui_path` for an HTML template. The media plugin writes
JSON metadata to `ui_path` and renders its HTML player from the built-in
template.

## Data Model Summary

Primary tables include:

- `users`
- `groups`
- `permission`
- `usergroup`
- `grouppermission`
- `dbsession`
- `apikey`
- `auditlog`
- `lock_records`

All live in docroot-local SQLite (`.adapt/adapt.db`).

## Caching Model

Current cache implementation is SQLite-backed (`adapt/cache.py`).

- cache table name: `cache`
- TTL-based entries
- resource-scoped invalidation
- used by plugins and admin cache endpoints

Caching is specific to each plugin. It is not one cache that covers every
FastAPI response. The CSV, Excel, and Parquet plugins cache parsed rows.
Adapt caches dataset schemas separately. The HTML and Markdown plugins cache
content that they render or read. The media plugin caches extracted
metadata. Adapt does not cache generic file response bodies or streamed
media bodies.

## Locking Model

Locking uses DB records with per-resource uniqueness and expiration.

- one lock record can exist per resource
- lock acquisition retries with exponential backoff
- Adapt can clean stale locks
- write operations use a lock context manager
- writable built-in dataset plugins replace the target atomically where supported

When lock acquisition exhausts all retries, Adapt returns `409 Conflict`.
Locking and atomic replacement reduce risk. Races can still occur. A write can
still stop before completion.

## Observability

- Python logging configured via `conf.json` `logging` section
- audit logs available via `/admin/audit-logs`
- successful REST and MCP dataset mutations create audit records
- health endpoint at `/health`

## Deployment Notes

Adapt optimizes the current implementation for single-instance, docroot-local operation.

Multi-instance operation, shared database and cache, and websocket-style real-time update architectures are future design topics, not current built-in behavior.

Manual navigation: [Previous: Plugin Development](plugin_development.md) | [Index](index.md) | [Next: Troubleshooting](troubleshooting.md)
