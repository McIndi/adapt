# User Guide

This guide explains day-to-day use of Adapt through its web UI and APIs.

## Landing Page

Visit `/` to see the landing page.

For authenticated users, the page shows accessible UI links based on
permissions. If upload support is enabled and the user has `write`
permission on the document-root boundary, the page also shows an upload
card that posts to `/api/uploads`.

For unauthenticated users:

- You can reach login at `/auth/login`.
- Access to generated resource routes depends on authentication and permissions.

Uploads require both authentication and explicit root-boundary write access.
If the configuration disables the feature, the upload card is hidden and the
API returns `403` for upload requests.

## Profile

Open `/profile` to change your password or manage your API keys. Before you
set a new password, enter your current password. Adapt signs you out of all
browser sessions after a successful change. Sign in with the new password.

Password changes do not revoke API keys. If a key must no longer authenticate,
revoke it separately.

## Generated UI Pages

For dataset resources (CSV, Excel sheets, Parquet), Adapt provides DataTables-based UIs at:

- `/ui/<resource>/`

Examples:

- `/ui/products/`
- `/ui/inventory/Stock/`

Typical capabilities include:

- Sort and filter table data
- Pagination
- Create, update, or delete rows through UI controls (unless the server is
  read-only)

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
curl -H "X-API-Key: your-key" http://localhost:8000/api/products/
```

### Dataset Write Contract

Dataset writes are action-based and target `/api/<resource>/`. API keys are
recommended for command-line writes because API-key-only requests are exempt
from CSRF validation.

Create:

```bash
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products/ \
  -d '{"action":"create","data":[{"name":"New Product","price":29.99}]}'
```

Update:

```bash
curl -X PATCH -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products/ \
  -d '{"action":"update","data":{"_row_id":1,"price":39.99}}'
```

Delete:

```bash
curl -X DELETE -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products/ \
  -d '{"action":"delete","data":{"_row_id":1}}'
```

### Schema Endpoint

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/schema/products/
```

Adapt validates supplied create and update values against this schema. An
unknown column or incompatible value returns `422` without changing the
file. Adapt normalizes numeric and boolean values entered in the generated
UI from their form strings. Blank values are still permitted. When
validation fails in the generated UI, its error message identifies the
column, expected type, and received type.

## Permissions and Access Control

Adapt uses users, groups, and resource permissions.

- `read` permissions control read access.
- `write` permissions control mutation access.
- Superusers bypass normal permission checks.

Generated API, schema, and UI routes all require authentication and the
appropriate permission. A non-superuser without `read` permission cannot
open the generated UI or schema route for that resource.

## Caching and Locks

- Caching is plugin-specific. Dataset plugins cache parsed rows. HTML and
  Markdown plugins cache content. Media plugins cache metadata. Generic
  file bodies and streamed media bodies are not cached.
- Mutations use locking to reduce concurrent write conflicts.
- You can inspect lock and cache state in the admin endpoints and UI.

## Troubleshooting

### `401` or `403` Responses

- Make sure that you are logged in, or that the API key is correct
- Make sure that group membership and permissions are correct

### Mutation Fails with `405`

- The server can be running with `--readonly`

### Mutation Fails with `409`

- Another operation holds the resource lock.
- Adapt also returns `409` when it exhausts all lock acquisition retries.
- Inspect `/admin/locks`.
- After the competing operation finishes, retry the write.

### Data Not Detected

- Make sure that the file extension is supported
- Make sure that the file is under the docroot
- Restart the server after you add files

## Best Practices

- Keep CSV, Excel, and Parquet schemas consistent
- Use group-based permissions rather than per-user exceptions
- Rotate or revoke API keys when they are no longer needed
- Use read-only mode for browse-only environments

Manual navigation: [Previous: Quick Start](quick_start.md) | [Index](index.md) | [Next: API Reference](api_reference.md)
