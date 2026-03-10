# API Reference

[Previous](user_guide) | [Next](admin_guide) | [Index](index)

This document describes the API surface that is currently implemented by Adapt.

## Authentication

Adapt supports two authentication methods:

1. Session cookie (`adapt_session`) from web login
2. API key using `X-API-Key: <key>`

Authentication endpoints:

- `GET /auth/login` - Login page (HTML)
- `POST /auth/login` - Login using form fields (`username`, `password`)
- `POST /auth/logout` - Logout current session
- `GET /auth/me` - Current authenticated user
- `GET /profile` - Authenticated profile page

User API key endpoints (for the currently authenticated user):

- `POST /api/apikeys`
- `GET /api/apikeys`
- `DELETE /api/apikeys/{key_id}` — deactivates the key (`is_active = false`), returns `204`. The key record is retained in the database but will no longer authenticate.

## Base URL

Default local URL: `http://localhost:8000`

## Generated Dataset APIs

For dataset resources (CSV, Excel sheets, Parquet), Adapt generates routes under:

- `/api/{resource}`
- `/schema/{resource}`
- `/ui/{resource}`

Examples:

- CSV `products.csv` -> `/api/products`
- Excel `inventory.xlsx` sheet `Stock` -> `/api/inventory/Stock`

### List Records

**GET** `/api/{resource}`

Query parameters:

- `limit` (optional)
- `offset` (optional, default `0`)
- `sort` (optional)
- `order` (optional: `asc` or `desc`, default `asc`)
- `filter` (optional JSON string)

Example:

```bash
curl -H "X-API-Key: key" "http://localhost:8000/api/products?limit=10&sort=name&order=asc"
```

### Mutations (Create, Update, Delete)

Adapt uses action-based mutation payloads at the collection endpoint.

**POST** `/api/{resource}`

```json
{
  "action": "create",
  "data": [
    {
      "name": "Keyboard",
      "price": 49.99,
      "category": "Electronics",
      "in_stock": true
    }
  ]
}
```

**PATCH** `/api/{resource}`

```json
{
  "action": "update",
  "data": {
    "_row_id": 1,
    "price": 39.99
  }
}
```

**DELETE** `/api/{resource}`

```json
{
  "action": "delete",
  "data": {
    "_row_id": 1
  }
}
```

Notes:

- Dataset mutations are row-oriented and use `_row_id`.
- In read-only mode, mutation endpoints return `405`.

## Schema Endpoint

**GET** `/schema/{resource}`

Returns the inferred or companion schema.

Example:

```bash
curl http://localhost:8000/schema/products
```

## Content Endpoints

For HTML and Markdown resources, Adapt mounts content routes using file path namespaces.

- HTML content route: `/{resource}`
- Markdown content route: `/{resource}`

Depending on mount namespace, resources may also be available with extension-qualified paths.

Examples:

- `readme.md` -> `/readme`
- `index.html` -> `/index`

## Media Endpoints

Media resources generate:

- Streaming endpoint: `/media/{resource}`
- Player UI: `/ui/{resource}`
- Gallery UI: `/ui/media`

Example:

```bash
curl -H "X-API-Key: key" http://localhost:8000/media/sample.mp4
```

## Python Handler Endpoints

Python handler files (`.py`) with an `APIRouter` named `router` are mounted under:

- `/api/{handler_name}`

Example:

- `reports.py` with `@router.get("/summary")` -> `/api/reports/summary`

## Admin Endpoints

All admin endpoints require superuser authentication and are prefixed with `/admin`.

Users:

- `GET /admin/users`
- `POST /admin/users`
- `DELETE /admin/users/{user_id}`

Groups:

- `GET /admin/groups`
- `GET /admin/groups/{group_id}`
- `POST /admin/groups`
- `DELETE /admin/groups/{group_id}`
- `POST /admin/groups/{group_id}/users/{user_id}`
- `DELETE /admin/groups/{group_id}/users/{user_id}`

Permissions:

- `GET /admin/permissions`
- `POST /admin/permissions`
- `DELETE /admin/permissions/{perm_id}`
- `GET /admin/groups/{group_id}/permissions`
- `POST /admin/groups/{group_id}/permissions/{perm_id}`
- `DELETE /admin/groups/{group_id}/permissions/{perm_id}`

Locks:

- `GET /admin/locks`
- `DELETE /admin/locks/{lock_id}`
- `POST /admin/locks/clean`

Cache:

- `GET /admin/cache`
- `DELETE /admin/cache`
- `DELETE /admin/cache/{key}` (requires `resource` query parameter)

API keys (admin-managed):

- `GET /admin/api-keys`
- `POST /admin/api-keys`
- `DELETE /admin/api-keys/{key_id}`

Audit logs:

- `GET /admin/audit-logs`

Admin UI page:

- `GET /admin/`

## System Endpoint

### Health

**GET** `/health`

- Unauthenticated callers receive base status info.
- Authenticated callers receive additional metrics.

Example fields:

- `status`
- `version`
- `timestamp`
- `uptime_seconds` (authenticated)
- `cache_size` (authenticated)
- `endpoint_count` (authenticated)

## Filtering, Sorting, and Pagination

Dataset and many admin list endpoints support:

- `filter` as JSON
- `sort`
- `order`
- `offset`
- `limit`

Supported filter operators include:

- `$eq`, `$ne`
- `$gt`, `$gte`, `$lt`, `$lte`
- `$contains`, `$startswith`, `$regex`
- `$and`

Example:

```bash
curl "http://localhost:8000/api/products?filter={\"price\":{\"$gte\":100},\"category\":\"Electronics\"}"
```

## Common Error Codes

- `400` - Invalid request data
- `401` - Not authenticated
- `403` - Permission denied
- `404` - Resource not found
- `405` - Method not allowed (including read-only mode mutations)
- `409` - Lock conflict

[Previous](user_guide) | [Next](admin_guide) | [Index](index)
