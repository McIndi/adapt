# Adapt

Adapt is a FastAPI server that turns files in a directory into APIs and UIs.

- Datasets (`.csv`, `.xlsx`, `.xls`, `.parquet`) become API endpoints and DataTables UIs
- Legacy `.xls` workbooks are read-only. Modern `.xlsx` workbooks support CRUD operations.
- Markdown/HTML become browsable pages
- Media files become streaming endpoints, plus player and gallery UIs
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
- **CSRF protection:** enforced for cookie-authenticated unsafe methods (`POST/PUT/PATCH/DELETE`), and covers mixed session and API-key requests
- **Redirect hardening:** login `next` paths are validated as local relative paths
- **Response hardening:** CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS (when TLS is enabled)
- **Host header hardening:** Trusted Host middleware
- **Data integrity:** lock-based, atomic writes for mutable dataset plugins
- **Auditability:** audit records for authentication, administration, and successful dataset mutations
- **Sensitive response cleanup:** admin user APIs no longer expose `password_hash`

### Important Deployment Notes

- Use TLS in non-local environments (`--tls-cert` and `--tls-key`). TLS makes secure cookies and HSTS protections effective.
- API-key-only clients are exempt from CSRF checks by design. Browser flows that use cookie authentication need CSRF tokens.

## Core Features

- Adaptive discovery and route generation
- Dataset CRUD with schema exposure
- Caching with invalidation on mutations
- Built-in admin UI for users/groups/permissions/locks/cache/api keys/audit logs
- Root-level file upload endpoint (`POST /api/uploads`) with permission checks and audit logging
- Optional landing-page upload card for authenticated users with root write permission
- Plugin architecture with companion overrides in `.adapt/`
- Permission-filtered full-text search across every resource type
- MCP server for agentic tool access, mounted alongside the REST API

Upload permission note:

- Non-superusers need `write` permission on the document-root boundary.
- In admin permission creation, use an empty resource (or `__root__`) with
  action `write`. Then assign that permission through a group.

## Full-Text Search

`GET /search?q=<query>` searches datasets, Markdown, HTML, and media metadata
in one ranked list. The search filters results to what the caller can read.
A query term that matches a resource you cannot see does not appear in the
results. It also does not appear in the result count.

```bash
curl -H "X-API-Key: <key>" "http://localhost:8000/search?q=parental+leave"
```

The index refreshes step by step on startup (`search_on_startup`, default
`true`). You can also rebuild it on demand with `adapt reindex <root>`. See
the [API Reference](docs/manual/api_reference.md#search-endpoint) for query
parameters and the result shape.

## MCP Interface

Adapt mounts a [Model Context Protocol](https://modelcontextprotocol.io)
server at `/mcp`. This server runs on the same host and port as the rest of
Adapt. It exposes five tools: `list_resources`, `get_schema`,
`read_resource`, `write_resource`, and `search`. Each tool uses the same
permission checks and plugin methods as the REST API. There is no separate
process, no separate API surface, and no extra permission model to
maintain.

Minimal walkthrough — create an account for the agent, grant it read access,
mint an API key, and connect a client:

```bash
adapt addsuperuser /path/to/docroot --username admin
adapt serve /path/to/docroot &

adapt admin create-permissions /path/to/docroot __all__
adapt admin create-user /path/to/docroot --username agent --password <strong-password>
adapt admin add-to-group /path/to/docroot --username agent --group <resource>_readonly
```

Log in as `agent`. From `/profile`, issue an API key for yourself. Any
authenticated user can create an API key for themself. A superuser is not
necessary for this step. Then point a client at `/mcp` with that key:

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

MCP does an authentication check when a tool runs. Tool calls use the shared
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

For `update` and `delete`, include the fields the operation needs, for
example `_row_id`.

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

## Helm (Kubernetes)

A Helm chart is included at `charts/adapt/`.

Uploads are disabled by default. To enable them, pass the upload environment
variables through Helm values. The container then uses the same
configuration as a local install.

**Ephemeral (default — data lost on pod restart):**

```bash
helm install adapt ./charts/adapt
```

**Dynamic persistent volume (cluster provisions storage automatically):**

```bash
helm install adapt ./charts/adapt \
  --set persistence.enabled=true \
  --set persistence.size=20Gi \
  --set persistence.storageClass=standard
```

**Existing PVC (cluster admin creates the PVC beforehand):**

```bash
# Cluster admin creates the PVC first, e.g.:
kubectl apply -f my-adapt-pvc.yaml

helm install adapt ./charts/adapt \
  --set persistence.enabled=true \
  --set persistence.existingClaim=my-adapt-pvc
```

Key persistence values:

| Value | Default | Description |
|---|---|---|
| `persistence.enabled` | `false` | Enable durable storage at `/data` |
| `persistence.existingClaim` | `""` | Name of a pre-created PVC to mount |
| `persistence.storageClass` | `""` | StorageClass name (cluster default if empty) |
| `persistence.accessModes` | `[ReadWriteOnce]` | PVC access modes |
| `persistence.size` | `10Gi` | Storage request size |
| `persistence.mountPath` | `""` (uses `adapt.rootPath`) | Mount path inside the container |
| `persistence.annotations` | `{}` | Annotations added to the PVC |

Example upload settings in `values.yaml`:

```yaml
env:
  - name: ADAPT_UPLOAD_ENABLED
    value: "true"
  - name: ADAPT_UPLOAD_MAX_SIZE_BYTES
    value: "10485760"
  - name: ADAPT_UPLOAD_ALLOWED_EXTENSIONS
    value: ".csv,.md,.txt"
  - name: ADAPT_UPLOAD_STRICT_MIME_SNIFFING
    value: "true"
```

When uploads are enabled, authenticated users with `write` permission on the
document-root boundary see the upload card on `/`. These users can upload
directly from the landing page.

> **Admin responsibility:** the cluster admin must supply a matching StorageClass
> and sufficient quota before enabling dynamic provisioning. For `ReadWriteOnce`
> volumes, keep `replicaCount=1` (the default).

**Bootstrap a superuser automatically** (requires `persistence.enabled=true`
— see [docs/manual/installation.md](docs/manual/installation.md#bootstrapping-a-superuser)
for why):

```bash
helm install adapt ./charts/adapt \
  --set persistence.enabled=true \
  --set bootstrapAdmin.enabled=true

# This example uses the release name "adapt".
kubectl get secret adapt-bootstrap-admin -o jsonpath='{.data.password}' | base64 -d && echo
```

For other release names, the Secret is usually
`<release>-adapt-bootstrap-admin`. If the release name contains `adapt`, the
name becomes `<release>-bootstrap-admin`. Run `helm get notes <release>` to
get the correct command.

**Expose it without an Ingress controller** (for example, bare-metal or k3s):

```bash
helm install adapt ./charts/adapt --set service.type=NodePort --set service.nodePort=30080
```

`charts/adapt/values-dev.yaml` bundles persistence, bootstrap, and a pinned
NodePort for local development on a VM or with k3s. See
[docs/manual/installation.md](docs/manual/installation.md#local-development-overlay)
for detail.

## Documentation

Read the full documentation at **https://www.mcindi.com/adapt/**.

More documentation is under `docs/manual/`.

- Manual index: [docs/manual/index.md](docs/manual/index.md)
- Security: [docs/manual/security.md](docs/manual/security.md)
- Quick start: [docs/manual/quick_start.md](docs/manual/quick_start.md)
- Configuration: [docs/manual/configuration.md](docs/manual/configuration.md)
- API reference: [docs/manual/api_reference.md](docs/manual/api_reference.md)
- MCP guide: [docs/manual/mcp_guide.md](docs/manual/mcp_guide.md)
- Plugin development: [docs/manual/plugin_development.md](docs/manual/plugin_development.md)
- Known limitations: [docs/manual/known_limitations.md](docs/manual/known_limitations.md)
- Release guide: [RELEASING.md](RELEASING.md)

Generated reference documentation is under `docs/reference/`. MkDocs builds
this documentation, and GitHub Pages publishes it.

- REST API reference: generated from app routes with an empty docroot
- OpenAPI schema artifact: generated from that same common-surface schema
- Python API reference: generated from docstrings and signatures

Build the documentation locally:

```bash
python -m pip install -e ".[dev]"
python -m pip install -r requirements-docs.txt
mkdocs build --strict
```

## License

MIT. See [LICENSE](LICENSE).
