# Adapt

Adapt is a FastAPI server that turns files in a directory into APIs and UIs.

- Datasets (`.csv`, `.xlsx`, `.parquet`) become CRUD endpoints and DataTables UIs
- Markdown/HTML become browsable pages
- Media files become streaming endpoints and player/gallery UIs
- Python files can register custom routers

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

- **Authentication:** session cookies and API keys (`X-API-Key`)
- **Authorization:** RBAC (users, groups, permissions), plus superuser bypass
- **Password security:** PBKDF2 hashing with per-user salts
- **Session security:** expiration enforcement, sliding renewal, cleanup task
- **CSRF protection:** enforced for cookie-authenticated unsafe methods (`POST/PUT/PATCH/DELETE`), including mixed session + API-key requests
- **Redirect hardening:** login `next` paths are validated as local relative paths
- **Response hardening:** CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS (when TLS is enabled)
- **Host header hardening:** Trusted Host middleware
- **Data integrity:** lock-based, atomic writes for mutable dataset plugins
- **Auditability:** admin/audit logging for security-relevant actions
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
adapt admin list-resources <root>
adapt admin create-permissions <root> __all__
```

## Documentation

Detailed docs live under `docs/manual/`.

- Manual index: [docs/manual/index.md](docs/manual/index.md)
- Security: [docs/manual/security.md](docs/manual/security.md)
- Quick start: [docs/manual/quick_start.md](docs/manual/quick_start.md)
- Configuration: [docs/manual/configuration.md](docs/manual/configuration.md)
- API reference: [docs/manual/api_reference.md](docs/manual/api_reference.md)
- Plugin development: [docs/manual/plugin_development.md](docs/manual/plugin_development.md)

## License

MIT. See [LICENSE](LICENSE).
