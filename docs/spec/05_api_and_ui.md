# Adapt Specification: API and UI

> **Status:** This document describes the current implementation. The running
> code on `main` wins if it differs. See the
> [documentation contract](../documentation-contract.md) and [user manual](../manual/index.md).

## 1. Generated routes

Discovery creates a resource registry. Each registry entry contains a plugin,
a descriptor, and its extensionless and extension-qualified namespaces. Adapt
mounts the routers from `Plugin.get_route_configs()` for both namespaces.

Generated routes require authentication and a matching resource permission.
`GET` uses the `read` action. `POST`, `PUT`, `PATCH`, and `DELETE` use the
`write` action. Superusers bypass resource permission checks.

Dataset resources provide trailing-slash routes under `/api/`, `/schema/`, and
`/ui/`. HTML and Markdown resources use extensionless content routes. Generic
files use direct content routes. Media resources use `/media/` and `/ui/`.

Python files can export an `APIRouter` named `router`. The Python plugin mounts
its routes under `/api/<namespace>`. Import errors cause the handler to be
skipped with a warning.

## 2. Landing page and discovery

The root route selects HTML or JSON from the `Accept` header.

The public HTML landing page gives unauthenticated users a sign-in link. It
does not show resource links. An authenticated user sees UI links for readable
resources. A superuser also sees the Admin UI link.

The JSON response contains resource paths that the caller can read. An
unauthenticated caller receives an empty resource list. A superuser receives
all discovered resource paths.

## 3. Dataset UI

The default DataTables UI supports sorting, search, pagination, row creation,
row updates, and row deletion. The UI hides mutation controls in read-only mode
or when the user does not have write permission.

Dataset plugins create missing `.adapt/*.index.html` files from
`datatable.html`. A companion template can replace the default UI. Adapt reads
the selected template during the request. The page fetches current rows from
the corresponding API route.

Unsafe cookie-authenticated requests require the CSRF cookie value in the
`X-CSRF-Token` header. Dataset companion templates receive a fetch wrapper that
adds this header.

## 4. Media routes

The shared `/ui/media` page lists media that the authenticated user can read.
Each media resource also has a player page and a `FileResponse` route.

The media plugin extracts available duration, bitrate, sample rate, channel,
and tag metadata through Mutagen. It attempts to create a JPEG thumbnail from
the one-second video frame. Metadata or thumbnail failures produce warnings
and do not stop discovery.

The plugin writes the extracted metadata and optional Base64 thumbnail to its
assigned companion `ui_path`. It does not cache streamed file bodies.

## 5. Admin UI and system routes

All `/admin/*` routes require a superuser. The Admin UI supports these actions:

* List, create, activate, deactivate, delete, and reset passwords for users
* List, create, and delete groups
* Add users to groups and remove them
* List, create, and delete permissions
* Add permissions to groups and remove them
* List, create, and revoke API keys
* List and filter audit records
* List and delete cache entries, or clear the cache
* List and release locks, or clean stale locks

The Profile UI lets a user change their password after they enter the current
password. The Admin UI lets a superuser reset any user password. Both actions
revoke all browser sessions for the affected user.

`GET /health` is a separate system route. It returns status, version, and time
to all callers. An authenticated caller also receives uptime, cache size, and
route count.

## 6. Errors

Adapt does not impose one error envelope on all code paths. Most application
errors and FastAPI request errors use a `detail` member.

```json
{
  "detail": "Not authenticated"
}
```

FastAPI validation errors return `422` with structured items in `detail`.
Dataset schema validation errors also return `422`; their `detail` string names
the column, expected type, and received type. The generated dataset UI displays
this detail for failed create and update operations. Validation runs before the
resource lock is acquired or the backing file is changed.

Immediate lock conflicts return `409`. Exhausted lock acquisition retries also
return `409`.

## 7. MCP interface

When `mcp_enabled` is true, Adapt mounts a FastMCP streamable HTTP application
at `/mcp/`. It uses the same process, TLS configuration, resource registry,
plugins, authentication resolver, and permission checks as the HTTP routes.

The server provides these tools:

| Tool | Purpose |
| --- | --- |
| `list_resources` | List namespaces that the caller can read |
| `get_schema` | Get schema metadata for a readable resource |
| `read_resource` | Read a resource and apply supported dataset query controls |
| `write_resource` | Create, update, or delete dataset rows |
| `search` | Search indexed content that the caller can read |

Authentication is enforced when a tool executes. MCP initialization and tool
discovery do not authenticate the caller. The shared resolver accepts the
`adapt_session` cookie or `X-API-Key` header. API keys are the supported and
recommended mechanism for MCP clients.

MCP does not expose user, group, permission, lock, cache, API key, or audit
administration. The `write_resource` tool rejects writes in read-only mode.
Successful `write_resource` calls create dataset audit records through the
shared mutation path.
