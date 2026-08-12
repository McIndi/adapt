# Troubleshooting

This guide covers common problems and verified troubleshooting steps for the current Adapt implementation.

## Server Startup Problems

### Port Already in Use

```bash
netstat -ano | findstr :8000
adapt serve . --port 8001
```

### Invalid Configuration

```bash
adapt check .
```

Look at `.adapt/conf.json` for invalid keys or JSON syntax errors.

### TLS Startup Error

If one TLS flag is provided without the other, startup fails.

Use both together:

```bash
adapt serve . --tls-cert /path/to/cert.pem --tls-key /path/to/key.pem
```

## Authentication Problems

### Login Fails

- Make sure that the username exists
- Make sure that the password is correct
- Make sure that the user is active

Useful checks:

```bash
adapt admin list-users .
sqlite3 .adapt/adapt.db "SELECT username, is_active FROM users;"
```

If the user is inactive, activate the user:

```bash
adapt admin activate-user . --username <username>
```

### API Key Returns 401

- Make sure that the header has this format: `X-API-Key: <key>`
- Make sure that the key is active and not expired
- Make sure that the key owner is active

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/auth/me
```

## Authorization Problems (`403`)

- Make sure that the group membership is correct
- Make sure that the resource permission names are correct
- Make sure that you use the correct action, `read` or `write`

Useful checks:

```bash
adapt admin list-groups .
adapt admin list-resources .
```

Generated API, schema, and UI routes require authentication plus the
corresponding resource permission. `create-permissions` creates individual
groups named `<resource>_readonly` and `<resource>_readwrite`. Combined group
names include a suffix made from all selected resources.

### Cookie-Authenticated Mutation Returns `403`

When an unsafe request uses the `adapt_session` cookie, it must also send the
`adapt_csrf` cookie value in the `X-CSRF-Token` header. This rule remains
true if the request also includes an API key. For command-line mutations,
use an API key without a session cookie to avoid CSRF handling.

## Resource Discovery Problems

### Files Not Appearing

- Make sure that the plugin registry contains the file extension.
- Make sure that the selected plugin detects the file.
- Make sure that the file is under docroot.
- Restart the server after you add files.

Supported built-in extensions are:

- Datasets: `.csv`, `.xlsx`, `.xls`, `.parquet`
- Rendered content: `.html`, `.md`
- Python handlers: `.py`
- Generic text and document files served by `FilePlugin`: `.txt`, `.pdf`,
  `.json`, `.xml`, `.svg`
- Generic image files served by `FilePlugin`: `.png`, `.jpg`, `.jpeg`, `.gif`,
  `.webp`
- Streamed media: `.mp4`, `.mp3`, `.avi`, `.mkv`, `.webm`, `.ogg`, `.wav`

Adapt discovers and reads legacy `.xls` files. These resources are read-only.
Convert a legacy workbook to `.xlsx` before you modify it through Adapt.
Unregistered extensions need a plugin mapping before Adapt can discover them.
See [Known Limitations](known_limitations.md#legacy-excel-files).

### Companion Files Missing

Run discovery check:

```bash
adapt check .
```

Companion files are generated under `.adapt/` for supported resource types.

## Dataset Write Problems

### `405 Method Not Allowed`

The server can be in read-only mode. A legacy `.xls` resource is also
read-only.

```bash
adapt serve . --readonly
```

### `409 Conflict`

When another operation holds the resource lock, Adapt returns `409`. Adapt
also returns this response when it exhausts all lock acquisition retries.

Inspect `/admin/locks` and the server log. Then retry the write after the
competing operation finishes.

### Write Payload Rejected

Dataset mutations require action envelope payloads on `/api/<resource>/`.

Example:

```json
{"action":"update","data":{"_row_id":1,"name":"Updated"}}
```

## Admin API Troubleshooting

Use implemented admin routes under `/admin`, for example:

- `/admin/users`
- `/admin/groups`
- `/admin/permissions`
- `/admin/locks`
- `/admin/cache`
- `/admin/api-keys`
- `/admin/audit-logs`

## Plugin Troubleshooting

### Custom Plugin Not Loading

Make sure that the class path format in `plugin_registry` is correct:

```json
{
  "plugin_registry": {
    ".ext": "module.path.ClassName"
  }
}
```

Current loader expects dotted class paths, not `module:path` syntax.

Make sure that the custom plugin `detect(path)` method returns `True` for the
file. When detection rejects the file, Adapt does not call `load(path)`.

### Import Errors

Do a manual test of the import:

```bash
python -c "from module.path import ClassName"
```

## Useful Diagnostic Commands

```bash
adapt check .
adapt list-endpoints .
adapt admin list-resources .
adapt reindex .
```

`adapt check` initializes storage and reports a discovered-resource count. It
also reports TLS file problems and top-level route collisions. It does not
migrate resource schemas or list each resource.

`adapt list-endpoints` builds the configured plugin routers and prints their
mounted resource paths. It includes sub-resources such as Excel sheets. It
does not invent API, schema, or UI paths for files that mount no routes.

`adapt reindex` rebuilds the full-text search index. Add `--force` to index
resources whose file metadata is unchanged.

## When to Collect Logs

When you report an issue, capture these logs:

- startup failure output
- traceback for 500 errors
- request path and response code
- relevant configuration from `.adapt/conf.json`

Manual navigation: [Previous: Architecture](architecture.md) | [Index](index.md) | [Next: Known Limitations](known_limitations.md)
