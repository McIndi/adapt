# Security

This guide documents security behavior currently implemented in Adapt.

## Authentication

Adapt authenticates with:

- Session cookie (`adapt_session`) after a local password login or Keycloak SSO
- API key (`X-API-Key`)
- Bearer JWT (`Authorization: Bearer`) when Keycloak OIDC is configured
- Local username and password at `POST /auth/login`, unless `oidc.local_login` is false

Login and logout routes:

- `GET /auth/login`
- `POST /auth/login`
- `GET /auth/oidc/login` and `GET /auth/oidc/callback` when OIDC is on
- `POST /auth/logout`

Session behavior:

- Session TTL is 7 days
- Sliding renewal on valid session usage
- Expired sessions are cleaned by a background task

API key behavior:

- Keys are stored as SHA-256 hashes
- Keys can be inactive or expired
- `last_used_at` is updated on successful key usage

All authentication methods require an active user. Inactive users cannot log
in or authenticate with an existing session or API key.

An administrator can deactivate a user in the Admin UI, API, or CLI.
Deactivation revokes browser sessions for the user. API keys remain stored but
cannot authenticate until an administrator activates the user.

The MCP interface (`/mcp/`, see the [MCP Guide](mcp_guide.md)) uses the same
authentication resolver as HTTP routes. Tool calls accept a session cookie,
an API key, or a Bearer JWT. API keys remain the simple option for scripts.
OAuth MCP clients (Cursor, Claude, VS Code) use Bearer tokens. When OIDC is
configured, an unauthenticated HTTP request to `/mcp/` returns `401` with a
`WWW-Authenticate` header that points at Adapt's protected-resource metadata.
Adapt still checks authentication when a tool executes. Cookie-authenticated
MCP requests are still subject to CSRF validation because the transport uses
HTTP POST.

## Keycloak OIDC

OIDC is off until both `oidc.issuer` and `oidc.client_id` are set (or the
matching `ADAPT_OIDC_*` environment variables). The client secret must come
from `ADAPT_OIDC_CLIENT_SECRET`, not `conf.json`.

Adapt is a relying party for the browser (authorization code and PKCE) and a
resource server for REST and MCP (JWT Bearer). It does not register OAuth
clients and it does not proxy Keycloak discovery. Keycloak remains the
authorization server.

On each successful OIDC login and each valid Bearer token, Adapt:

- Uses `preferred_username` (or `oidc.username_claim`) as the Adapt username
- Creates the user if needed, with a password hash that cannot log in locally
- Rejects inactive users
- Maps Keycloak `groups` (path prefix stripped) and `realm_access.roles` onto
  existing Adapt groups of the same name
- Sets `is_superuser` when a configured role is present (default `adapt-admin`)
- Removes only group memberships that OIDC previously added (`oidc_managed`)

Unknown Keycloak group names are ignored. Run `adapt admin create-permissions`
so Keycloak groups can match `<resource>_readonly` and `<resource>_readwrite`.
Do not expect Adapt to create groups from Keycloak.

Operator checklist for Keycloak 26.6 or later:

- Confidential client `adapt-web`: authorization code and PKCE, redirect
  `{public_url}/auth/oidc/callback`, logout redirect `{public_url}/auth/login`
- Audience mapper so access tokens carry `aud` equal to Adapt `public_url`
  (or RFC 8707 `RESOURCE_INDICATOR` on Keycloak 26.8+)
- Group membership mapper onto the `groups` claim
- Realm role `adapt-admin` for Adapt superusers
- Realm dynamic client registration (DCR) enabled so MCP clients can register
  themselves with Keycloak
- Groups named to match Adapt groups (`products_readonly`, and so on)

## Authorization

Adapt enforces resource permissions through users, groups, and permissions.

- Superusers bypass standard permission checks
- Generated resource routes are mounted with permission dependencies
- `read` is required for GET
- `write` is required for POST/PATCH/DELETE

## Password Security

Password handling:

- PBKDF2-HMAC-SHA256
- 100,000 iterations
- Per-user random salt
- Constant-time comparison for verification

Users can change their password in the Profile UI. They must enter their
current password. The new password must pass the password-strength check.

Administrators can reset a user password in the Admin UI, admin API, or CLI.
Each password change revokes all browser sessions for that user. API keys stay
active and must be revoked separately.

## CSRF Protection

CSRF is enforced for unsafe HTTP methods when session cookies are involved.

Key points:

- CSRF cookie name: `adapt_csrf`
- CSRF header name: `X-CSRF-Token`
- Form field fallback: `csrf_token`
- API-key-only requests without session cookies are exempt
- Bearer-only requests without session cookies are exempt
- If a session cookie is present, CSRF still applies even when an API key or
  Bearer token is also sent

The `/docs` Swagger UI reads the `adapt_csrf` cookie and sends it as
`X-CSRF-Token` on Try it out requests. Cookie login (password or Keycloak)
can mutate resources from API Docs. curl and other clients still have to
set the header themselves.

For example, log in and store the session and CSRF cookies in a curl cookie
jar. Then copy the CSRF cookie into the header for an unsafe request:

```bash
curl -c /tmp/adapt-cookies.txt -X POST \
  --data-urlencode "username=admin" \
  --data-urlencode "password=<password>" \
  http://localhost:8000/auth/login

CSRF_TOKEN=$(awk '$6 == "adapt_csrf" {print $7}' /tmp/adapt-cookies.txt)
curl -b /tmp/adapt-cookies.txt -X POST \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/products/ \
  -d '{"action":"create","data":[{"name":"Keyboard"}]}'
```

For command-line mutations, an API-key-only request is simpler and does not
require CSRF handling.

## Security Headers

Adapt sets security headers on responses:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy: ...` (policy configured in code)
- `Strict-Transport-Security` when TLS is enabled

## Host Header Protection

Adapt uses `TrustedHostMiddleware`. The allowed hosts come from the configured host.

## TLS and Cookies

When the configuration sets a TLS certificate and key together:

- HTTPS is active
- HSTS is active
- The server configuration turns on secure-cookie behavior

## Locking and Safe Writes

Dataset write paths use lock management and atomic replacement to reduce corruption and race risks.

Lock behavior includes:

- Per-resource lock records
- Retry with exponential backoff
- Timeout-based acquisition failure
- Stale lock cleanup
- Atomic target replacement for built-in dataset plugins where the platform
  supports it

These mechanisms reduce concurrency and partial-write risks. They do not make
writes uninterruptible or remove every race. Adapt returns `409 Conflict` when
lock acquisition exhausts all retries.

## Row-Level Filtering

`Plugin.filter_for_user()` is an extension point that dataset reads use. The
built-in plugins do not apply per-user row filters. Dataset writes read and
rewrite row collections. This process does not safely enforce write-level
row security. Plugins must not treat this hook as authorization
for row-level mutations.
See [Known Limitations](known_limitations.md#write-level-row-security).

## Audit and Admin Security Endpoints

Superuser endpoints include:

- `/admin/users`
- `/admin/groups`
- `/admin/permissions`
- `/admin/locks`
- `/admin/cache`
- `/admin/api-keys`
- `/admin/audit-logs`

Adapt records these events:

- Successful login and logout
- API-key creation and revocation
- User and group creation or deletion
- User activation and deactivation
- Group membership changes
- Permission creation, deletion, and assignment changes
- Manual lock operations
- Cache deletion and clearing
- Successful dataset creation, update, and deletion operations

REST and MCP dataset mutations use the shared audit path. The record contains
the user, source IP, dataset path, action, timestamp, and mutation summary.
The record does not contain dataset values.

Audit records describe successful operations. If you need a history that
includes failed requests, use trusted reverse-proxy access logs.

## File uploads

Uploads are off by default (`upload.enabled` / `ADAPT_UPLOAD_ENABLED`).
`POST /api/uploads` is the only write path that creates a new file in the
document root from an HTTP client.

Authorization:

- The caller must authenticate.
- The caller must have `write` on the document root (`""`). Superusers have
  this permission. Other users need an explicit grant.
- Read-only mode (`--readonly`) rejects uploads with `405`.

Path traversal:

- The `filename` field must be a single basename. Slashes, backslashes,
  absolute paths, `..` segments, hidden names, and directories are rejected.
- The resolved target must stay in the document root. Symlinks that escape
  the root are rejected.

Size limits:

- The default limit is 10 MiB (`upload.max_size_bytes` /
  `ADAPT_UPLOAD_MAX_SIZE_BYTES`).
- The handler counts bytes while it writes. A payload over the limit
  returns `413`.

Content type and MIME confusion:

- Extension allow and deny lists apply first (`allowed_extensions`,
  `denied_extensions`).
- Strict MIME sniffing is off by default. When
  `upload.strict_mime_sniffing` is true, Adapt sniffs the first 4096 bytes
  and compares that type with the filename extension and the provided
  `Content-Type`. A mismatch returns `400`.
- Optional `allowed_mime_types` applies only when strict sniffing is on.

Collision:

- Default policy is `overwrite`. Set `collision_policy` to `reject` to
  return `409` when the file already exists.

Successful and denied uploads write audit records (`upload_success`,
`upload_denied`, `upload_failed`). A new file also gets an owner group
(`upload_owner_<filename>`) with read and write on the discovered resource.

## Practical Checks

```bash
# Current user
curl -H "X-API-Key: <key>" http://localhost:8000/auth/me

# Audit logs (superuser)
curl -H "X-API-Key: <superuser-key>" http://localhost:8000/admin/audit-logs

# Health
curl http://localhost:8000/health
```

## Recommendations

- Always use TLS in non-local environments.
- Rotate API keys.
- Deactivate unused API keys.
- Keep superuser accounts limited and monitored.
- Review audit logs regularly.

Manual navigation: [Previous: Admin Guide](admin_guide.md) | [Index](index.md) | [Next: MCP Guide](mcp_guide.md)
