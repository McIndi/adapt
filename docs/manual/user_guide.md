# User Guide

[Previous](quick_start) | [Next](api_reference) | [Index](index)

This guide explains day-to-day use of Adapt through its web UI and APIs.

## Landing Page

Visit `/` to see the landing page.

For authenticated users, the page shows accessible UI links based on permissions.

For unauthenticated users:

- You can reach login at `/auth/login`.
- Access to generated resource routes depends on authentication and permissions.

## Generated UI Pages

For dataset resources (CSV, Excel sheets, Parquet), Adapt provides DataTables-based UIs at:

- `/ui/<resource>`

Examples:

- `/ui/products`
- `/ui/inventory/Stock`

Typical capabilities include:

- Sort and filter table data
- Pagination
- Create/update/delete via UI controls (unless server is read-only)

## Content Pages

### HTML Files

HTML resources are served at path-based routes such as `/index`.

### Markdown Files

Markdown resources are rendered as HTML at routes such as `/readme`.

## Media

If media files are discovered, Adapt provides:

- `/ui/media` - media gallery
- `/ui/<media-resource>` - individual player page
- `/media/<media-resource>` - streaming endpoint

## API Usage

### Authentication Options

For API calls, use either:

1. Session cookie from login
2. `X-API-Key` header

### Dataset Read

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/products
```

### Dataset Write Contract

Dataset writes are action-based and target `/api/<resource>`.

Create:

```bash
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products \
  -d '{"action":"create","data":[{"name":"New Product","price":29.99}]}'
```

Update:

```bash
curl -X PATCH -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products \
  -d '{"action":"update","data":{"_row_id":1,"price":39.99}}'
```

Delete:

```bash
curl -X DELETE -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products \
  -d '{"action":"delete","data":{"_row_id":1}}'
```

### Schema Endpoint

```bash
curl http://localhost:8000/schema/products
```

## Permissions and Access Control

Adapt uses users, groups, and resource permissions.

- `read` permissions control read access.
- `write` permissions control mutation access.
- Superusers bypass normal permission checks.

## Caching and Locks

- Read responses are cached using SQLite-backed cache tables.
- Mutations use locking to reduce concurrent write conflicts.
- Lock and cache state can be inspected in the admin endpoints/UI.

## Troubleshooting

### `401` or `403` Responses

- Verify login or API key
- Confirm group membership and permissions

### Mutation Fails with `405`

- Server may be running with `--readonly`

### Mutation Fails with `409`

- A lock conflict occurred; retry after a short delay

### Data Not Detected

- Confirm file extension is supported
- Confirm file is under docroot
- Restart server after adding files

## Best Practices

- Keep CSV/Excel/Parquet schemas consistent
- Use group-based permissions rather than per-user exceptions
- Rotate/revoke API keys when no longer needed
- Use read-only mode for browse-only environments

[Previous](quick_start) | [Next](api_reference) | [Index](index)
