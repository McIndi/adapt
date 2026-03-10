# Architecture

[Previous](plugin_development) | [Next](troubleshooting) | [Index](index)

This document describes the current Adapt architecture.

## High-Level Design

Adapt is a FastAPI application that:

1. Loads configuration from `DOCROOT/.adapt/conf.json`
2. Initializes SQLite-backed storage and cache
3. Discovers resources in docroot using extension-to-plugin mapping
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
- Plugin `load()` returns one or more resource descriptors
- Companion files may be generated under `.adapt/`
- Route configs from plugin are mounted into the app

### Data and Security Layer

Key modules:

- `adapt/storage.py` (SQLModel tables + DB engine)
- `adapt/auth/*` (sessions, password, dependencies)
- `adapt/security.py` (CSRF + security headers)
- `adapt/locks.py` (lock manager)
- `adapt/cache.py` (SQLite-backed cache)

## Implemented Middleware and Security Flow

Current middleware stack includes:

- Trusted host middleware
- security middleware (CSRF validation + security headers)
- auth middleware (session user hydration)

Request flow for unsafe methods with session authentication:

1. CSRF token validated (`adapt_csrf` cookie + `X-CSRF-Token`)
2. user resolved from session or API key
3. endpoint dependency checks permission
4. route handler executes

## Route Generation Model

For each resource, plugins provide `(prefix, router)` pairs.

Routes are mounted with permission dependencies and namespace variants.

Common prefixes:

- `api`
- `schema`
- `ui`
- `media`

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

## Locking Model

Locking uses DB records with per-resource uniqueness and expiration.

- lock acquisition retries with exponential backoff
- stale locks can be cleaned
- write operations use lock context manager

## Observability

- Python logging configured via `conf.json` `logging` section
- audit logs available via `/admin/audit-logs`
- health endpoint at `/health`

## Deployment Notes

Current implementation is optimized for single-instance docroot-local operation.

Multi-instance, shared DB/cache, and websocket-style real-time update architectures are future design topics, not current built-in behavior.

[Previous](plugin_development) | [Next](troubleshooting) | [Index](index)
