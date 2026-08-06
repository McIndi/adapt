# Adapt

Adapt is a FastAPI server that turns files in a directory into APIs and UIs.

- Datasets (`.csv`, `.xlsx`, `.xls`, `.parquet`) become API endpoints and DataTables UIs
- Legacy `.xls` workbooks are read-only. Modern `.xlsx` workbooks support CRUD operations.
- Markdown/HTML become browsable pages
- Media files become streaming endpoints and player/gallery UIs
- Python files can register custom routers
- Everything is searchable in one place via full-text `/search`
- Everything is reachable by agentic tools via an MCP server at `/mcp`

## Quick Start

```bash
pip install adapt-server
adapt addsuperuser --username admin /path/to/docroot
adapt serve /path/to/docroot

# Generate permissions for all discovered resources
adapt admin create-permissions /path/to/docroot __all__

# Everything below here can be done in the admin UI at
# http://localhost:8000/admin/ after logging in with the superuser account.
#
# Create a regular user
adapt admin create-user --username editor --password secret /path/to/docroot

# Reset an existing password and revoke that user's browser sessions
adapt admin change-password --username editor /path/to/docroot

# By default, the editor user has no permissions.
# See available groups (created by `adapt admin create-permissions`) and assign user to desired group
adapt admin list-groups /path/to/docroot
adapt admin add-to-group --username editor --group <group_name> /path/to/docroot
```

Useful URLs:

- `/` landing page
- `/admin/` admin UI
- `/api/<resource>` resource API
- `/ui/<resource>` resource UI
- `/schema/<resource>` resource schema
- `/search` full-text search across every resource you can read
- `/mcp` MCP server for agentic tools (see [MCP Interface](#mcp-interface) below)

## What Adapt Generates

From files in your docroot, Adapt auto-discovers resources and mounts routes with extensionless URLs where possible.

Example:

```text
data/
  employees.csv
  sales.xlsx
  video.mp4
  readme.md
  stats.py
```

Rough output:

- `/api/employees`, `/ui/employees`, `/schema/employees`
- `/api/sales/<sheet>`, `/ui/sales/<sheet>`
- `/media/video.mp4`, `/ui/video.mp4`, `/ui/media`
- `/readme`
- `/api/stats/*`

## Current Security Posture

This reflects the current implementation in the codebase.

### In Place

- **Authentication:** session cookies, API keys (`X-API-Key`), and inactive-user enforcement
- **Authorization:** RBAC (users, groups, permissions), plus superuser bypass
- **Password security:** PBKDF2 hashing with per-user salts
- **Password changes:** self-service and administrator resets revoke all browser sessions for the user
- **Session security:** expiration enforcement, sliding renewal, cleanup task
- **CSRF protection:** enforced for cookie-authenticated unsafe methods (`POST/PUT/PATCH/DELETE`), including mixed session + API-key requests
- **Redirect hardening:** login `next` paths are validated as local relative paths
- **Response hardening:** CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS (when TLS is enabled)
- **Host header hardening:** Trusted Host middleware
- **Data integrity:** lock-based, atomic writes for mutable dataset plugins
- **Auditability:** audit records for authentication, administration, and successful dataset mutations
- **Sensitive response cleanup:** admin user APIs no longer expose `password_hash`

### Important Deployment Notes

- Use TLS in non-local environments (`--tls-cert` + `--tls-key`) so secure cookies and HSTS protections are effective.
- API-key-only clients are exempt from CSRF checks by design; cookie-auth browser flows require CSRF tokens.

## Core Features

- Adaptive discovery and route generation
- Dataset CRUD with schema exposure
- Caching with invalidation on mutations
- Built-in admin UI for users/groups/permissions/locks/cache/api keys/audit logs
- Plugin architecture with companion overrides in `.adapt/`
- Permission-filtered full-text search across every resource type
- MCP server for agentic tool access, mounted alongside the REST API

## Full-Text Search

`GET /search?q=<query>` searches datasets, Markdown, HTML, and media metadata
in one ranked list, filtered to what the caller may read — a query term that
matches a resource you can't see never shows up, and never leaks via the
result count either.

```bash
curl -H "X-API-Key: <key>" "http://localhost:8000/search?q=parental+leave"
```

The index refreshes incrementally on startup (`search_on_startup`, default
`true`) and can be rebuilt on demand with `adapt reindex <root>`. See the
[API Reference](docs/manual/api_reference.md#search-endpoint) for query
parameters and result shape.

## MCP Interface

Adapt mounts a [Model Context Protocol](https://modelcontextprotocol.io)
server at `/mcp`, on the same host/port as everything else, exposing five
tools that wrap the same permission checks and plugin methods as the REST
API — `list_resources`, `get_schema`, `read_resource`, `write_resource`, and
`search`. There's no separate process, no separate API surface, and no
extra permission model to maintain.

Minimal walkthrough — create an account for the agent, grant it read access,
mint an API key, and connect a client:

```bash
adapt addsuperuser /path/to/docroot --username admin
adapt serve /path/to/docroot &

adapt admin create-permissions /path/to/docroot __all__
adapt admin create-user /path/to/docroot --username agent --password <strong-password>
adapt admin add-to-group /path/to/docroot --username agent --group <resource>_readonly
```

Log in as `agent` and self-issue an API key from `/profile` (any
authenticated user can create their own key — no superuser needed), then
point a client at `/mcp` with that key:

```bash
# Claude Code CLI
claude mcp add --transport http adapt http://localhost:8000/mcp \
  --header "X-API-Key: <key>"
```

```json
// Generic MCP client config (Claude Desktop and similar)
{
  "mcpServers": {
    "adapt": {
      "url": "http://localhost:8000/mcp",
      "headers": { "X-API-Key": "<key>" }
    }
  }
}
```

MCP checks authentication when a tool runs. Tool calls use the shared
authentication resolver, which accepts a session cookie or an API key. API
keys are the supported and recommended mechanism for MCP clients. Set
`mcp_enabled: false` in `.adapt/conf.json` (or `ADAPT_MCP_ENABLED=false`) to
remove `/mcp` entirely. For setup and troubleshooting, read the
[MCP guide](docs/manual/mcp_guide.md).
For dataset reads, `sort` is the column name and `order` must be `asc` or
`desc`.

## Dataset Mutation Envelope

For dataset endpoints, write operations use this payload structure:

```json
{
  "action": "create|update|delete",
  "data": []
}
```

Use object data for `update`/`delete` as needed (for example, with `_row_id`).

## CLI (Common Commands)

```bash
adapt serve <root> [--host ... --port ... --tls-cert ... --tls-key ... --reload --readonly --debug]
adapt check <root>
adapt addsuperuser <root> --username <name>
adapt list-endpoints <root>
adapt reindex <root> [--force]
adapt admin list-resources <root>
adapt admin create-permissions <root> __all__
```

Use `--reload` during development. Uvicorn watches Python files in the document
root and restarts Adapt after a change.

## Documentation

Detailed docs live under `docs/manual/`.

- Manual index: [docs/manual/index.md](docs/manual/index.md)
- Security: [docs/manual/security.md](docs/manual/security.md)
- Quick start: [docs/manual/quick_start.md](docs/manual/quick_start.md)
- Configuration: [docs/manual/configuration.md](docs/manual/configuration.md)
- API reference: [docs/manual/api_reference.md](docs/manual/api_reference.md)
- MCP guide: [docs/manual/mcp_guide.md](docs/manual/mcp_guide.md)
- Plugin development: [docs/manual/plugin_development.md](docs/manual/plugin_development.md)
- Known limitations: [docs/manual/known_limitations.md](docs/manual/known_limitations.md)

Generated reference docs live under `docs/reference/` and are published via
MkDocs and GitHub Pages.

- REST API reference: generated from app routes with an empty docroot
- OpenAPI schema artifact: generated from that same common-surface schema
- Python API reference: generated from docstrings and signatures

Build docs locally:

```bash
python -m pip install -e ".[dev]"
python -m pip install -r requirements-docs.txt
mkdocs build --strict
```

## License

MIT. See [LICENSE](LICENSE).
