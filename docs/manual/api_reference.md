# API Reference

This document describes the API surface that is currently implemented by Adapt.

## Authentication

Adapt supports two authentication methods:

1. Session cookie (`adapt_session`) from web login
2. API key using `X-API-Key: <key>`

Generated resource routes require authentication. Non-superusers must also
have the corresponding `read` or `write` permission. For command-line
mutations, prefer an API key because an API-key-only request is CSRF-exempt.
Cookie-authenticated unsafe requests must send the `adapt_csrf` cookie value
in the `X-CSRF-Token` header (or in the `csrf_token` form field).

Each authentication method requires an active user. An inactive user cannot
log in or authenticate with an existing session or API key.

Authentication endpoints:

- `GET /auth/login` - Login page (HTML)
- `POST /auth/login` - Login using form fields (`username`, `password`)
- `POST /auth/logout` - Logout current session
- `GET /auth/me` - Current authenticated user
- `PUT /auth/password` - Change the current user password
- `GET /profile` - Authenticated profile page

`PUT /auth/password` accepts `current_password` and `new_password`. A
successful change revokes all browser sessions for the user and returns a
message that tells the user to sign in again. The new password must pass the
password-strength check.

User API key endpoints (for the currently authenticated user):

- `POST /api/apikeys`
- `GET /api/apikeys`
- `DELETE /api/apikeys/{key_id}` — deactivates the key (`is_active = false`) and returns `204`. Adapt keeps the key record in the database, but the key will no longer authenticate.

## Base URL

Default local URL: `http://localhost:8000`

## Hosted vs Runtime API Schema

Adapt publishes two intentionally different OpenAPI views:

- **Hosted documentation schema** (this documentation site): generated from an app built
  with an empty docroot, so it documents only the API surface shared by all
  Adapt deployments.
- **Runtime schema** (`GET /openapi.json` on a live server): generated per
  request and filtered by authentication, permissions, and discovered resources
  in that instance's docroot.

Runtime routes depend on discovered files and caller permissions. As a result,
a live instance can expose more paths, or fewer visible paths, than the
hosted documentation shows.

## Generated Dataset APIs

For dataset resources (CSV, Excel sheets, Parquet), Adapt generates routes under:

- `/api/{resource}/`
- `/schema/{resource}/`
- `/ui/{resource}/`

Examples:

- CSV `products.csv` -> `/api/products/`
- Excel `inventory.xlsx` sheet `Stock` -> `/api/inventory/Stock/`
- Legacy Excel `inventory.xls` sheet `Stock` -> `/api/inventory/Stock/`

Legacy `.xls` routes support read and schema requests. Their mutation requests
return `405` because legacy workbooks are read-only.

### List Records

**GET** `/api/{resource}/`

Query parameters:

- `limit` (optional)
- `offset` (optional, default `0`)
- `sort` (optional)
- `order` (optional: `asc` or `desc`, default `asc`)
- `filter` (optional JSON string)

Example:

```bash
curl -H "X-API-Key: key" "http://localhost:8000/api/products/?limit=10&sort=name&order=asc"
```

### Mutations (Create, Update, Delete)

Adapt uses action-based mutation payloads at the collection endpoint.

**POST** `/api/{resource}/`

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

**PATCH** `/api/{resource}/`

```json
{
  "action": "update",
  "data": {
    "_row_id": 1,
    "price": 39.99
  }
}
```

**DELETE** `/api/{resource}/`

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
- Adapt validates create and update values against the inferred or companion
  schema before it locks or changes the backing file. Unknown columns and
  incompatible values return `422`.
- Adapt accepts and normalizes numeric and boolean strings from the generated
  HTML form. Blank strings and `null` remain valid because Adapt schemas do
  not describe nullability or required columns.
- In read-only mode, mutation endpoints return `405`.
- Legacy `.xls` resources are always read-only and return `405` for mutations.

## Schema Endpoint

**GET** `/schema/{resource}/`

Returns the inferred or companion schema.

For CSV and Excel resources, inference assigns only `string`, `integer`,
`number`, or `boolean`. These types control response serialization and the
default dataset UI columns. Adapt also uses these types to make sure that
values in create and update mutations are correct. For Parquet resources,
Adapt makes sure that the common Parquet type names correspond to these four
types. An unrecognized custom type remains metadata only.

The schema format does not currently express required columns or nullability.
Adapt validates fields that the caller supplies and permits blank or `null`
values. A validation failure uses status `422`, for example:

```json
{
  "detail": "Schema validation failed: column 'price': expected number, received string"
}
```

Example:

```bash
curl -H "X-API-Key: key" http://localhost:8000/schema/products/
```

## Content Endpoints

For HTML and Markdown resources, Adapt mounts content routes using file path namespaces.

- HTML content route: `/{resource}`
- Markdown content route: `/{resource}`

Some resources are also available with extension-qualified paths. This depends on the mount namespace.

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

## Search Endpoint

**GET** `/search`

Full-text search covers every resource that the caller can read. Datasets,
Markdown, HTML, and media metadata all rank in one result list. Adapt filters
results by permission after it queries the index. As a result, `count` never
reveals the existence of a resource that the caller cannot see.

Query parameters:

- `q` (optional, an empty value returns no results)
- `limit` (optional, default `20`, max `100`)
- `offset` (optional, default `0`)
- `type` (optional, comma-separated resource types, for example `csv,markdown`)

Example:

```bash
curl -H "X-API-Key: key" "http://localhost:8000/search?q=parental+leave&type=csv,markdown"
```

Returns JSON by default, or an HTML results page when the client sends
`Accept: text/html`. Each result includes `resource`, `type`, `title`,
`snippet`, `score`, and `ui_url`. Dataset row hits also include `api_url` and
`row_id`.

Adapt rebuilds the index incrementally on server startup (`search_on_startup`,
default `true`). You can also rebuild the index on demand:

```bash
adapt reindex /path/to/docroot [--force]
```

## Upload Endpoint

**POST** `/api/uploads`

Uploads a single file to the document root. The endpoint accepts multipart form
data with these fields:

- `filename` (required): basename only, no path separators
- `file` (required): binary file payload

Example:

```bash
curl -X POST \
  -H "X-API-Key: key" \
  -F "filename=notes.txt" \
  -F "file=@./notes.txt" \
  http://localhost:8000/api/uploads
```

Response example:

```json
{
  "path": "notes.txt",
  "size": 42,
  "mime_type": "text/plain",
  "checksum": "<sha256>",
  "operation": "created"
}
```

Behavior notes:

- Requires authenticated user with `write` permission on the document-root boundary.
- Returns `405` when global read-only mode is enabled.
- Returns `403` when upload feature is disabled (`upload.enabled=false`) or permission check fails.
- Rejects path traversal and path-separator input in `filename`.
- Uses atomic write semantics and returns `operation` as `created` or `overwritten`.
- Invalidates cache for the written resource and emits upload audit events.
- The configuration key `upload.strict_mime_sniffing` controls optional
  strict MIME sniffing. When enabled, Adapt validates sniffed content
  against the filename extension and the optional `upload.allowed_mime_types`
  list.
- The configuration key `upload.collision_policy` controls collision
  handling: `overwrite` (default) or `reject` (returns `409` when the target
  exists).
- The landing page (`/`) shows the same upload form for authenticated users
  with root-boundary `write` permission when `upload.enabled=true`.

To grant upload permission to a non-superuser through admin APIs, create a
`write` permission on the document-root boundary resource (`""`). The admin API
accepts `""` directly. It also normalizes `"__root__"` or `"<root>"` to the
same boundary value.

Example:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <csrf>" \
  -b "adapt_session=<session-cookie>" \
  -d '{"resource":"__root__","action":"write","description":"Root upload write"}' \
  http://localhost:8000/admin/permissions
```

## MCP Interface

Adapt mounts a [Model Context Protocol](https://modelcontextprotocol.io)
server at `/mcp/`. The server exposes the same permission-filtered
read, write, and search features as tools for agentic clients. See the
[MCP Guide](mcp_guide.md) for a full walkthrough from account creation to
connecting a client.

| Tool | Equivalent to |
|---|---|
| `list_resources` | `GET /` (JSON) |
| `get_schema` | `GET /schema/{resource}/` |
| `read_resource` | `GET /api/{resource}/` |
| `write_resource` | `POST`/`PATCH`/`DELETE /api/{resource}/` |
| `search` | `GET /search` |

Adapt enforces authentication when a tool executes, not while the client
initializes or discovers tools. MCP uses Adapt's shared authentication
resolver, which accepts either a session cookie or an API key. API keys are
the supported and recommended mechanism for MCP clients. Set
`mcp_enabled: false` in `.adapt/conf.json` (or `ADAPT_MCP_ENABLED=false`) to
remove `/mcp/` entirely.

## Admin Endpoints

All admin endpoints require superuser authentication and are prefixed with `/admin`.

Users:

- `GET /admin/users`
- `POST /admin/users`
- `PUT /admin/users/{user_id}/password`
- `PUT /admin/users/{user_id}/status`
- `DELETE /admin/users/{user_id}`

The password-reset request contains `new_password`. A successful reset revokes
all browser sessions for the target user. It does not revoke API keys.

The status request contains the Boolean `is_active` value. Deactivation
revokes browser sessions. API keys remain stored and cannot authenticate
until an administrator activates the user.

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

Adapt currently creates audit entries for:

- Successful login and logout
- Password changes and administrator resets
- API-key creation and revocation
- User and group creation or deletion
- Group membership changes
- Permission creation, deletion, and group assignment changes
- Manual lock release and stale-lock cleanup
- Cache entry deletion and cache clearing
- Upload success, deny, and failure attempts
- Successful dataset creation, update, and deletion operations

Dataset mutations use these audit actions:

| Mutation | Audit action |
|---|---|
| `POST` create | `create_dataset_rows` |
| `PATCH` update | `update_dataset_row` |
| `DELETE` delete | `delete_dataset_row` |

Upload events use these actions:

| Result | Audit action |
|---|---|
| Success (create/overwrite) | `upload_success` |
| Permission/config deny | `upload_denied` |
| Validation/write failure | `upload_failed` |

The audit resource is the dataset path relative to the document root. The path
includes the file extension and an Excel sheet namespace when applicable.

The details contain the created row count or the affected row ID. They do not
contain dataset values.

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
curl -H "X-API-Key: key" "http://localhost:8000/api/products/?filter={\"price\":{\"$gte\":100},\"category\":\"Electronics\"}"
```

## Common Error Codes

- `400` - Invalid request data
- `401` - Not authenticated
- `403` - Permission denied
- `404` - Resource not found
- `405` - Method not allowed (for example, read-only mode mutations)
- `409` - Lock acquisition conflicts
- `422` - FastAPI request or parameter validation failure

Error bodies are not a single Adapt-specific envelope. FastAPI-generated and
most application errors use a `detail` member, for example:

```json
{"detail": "Not authenticated"}
```

Validation failures can use a list of structured objects under `detail`.
Adapt returns `409` when another operation holds the resource lock. This
response also applies when Adapt exhausts all lock acquisition retries.

Manual navigation: [Previous: User Guide](user_guide.md) | [Index](index.md) | [Next: Admin Guide](admin_guide.md)
