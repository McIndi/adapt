# Security Policy

## Supported Versions

Adapt is pre-1.0 (currently `0.5.x`). Only the latest published release on
PyPI is supported with security fixes. There is no LTS branch yet.

| Version | Supported |
|---------|-----------|
| 0.5.x   | Yes |
| < 0.5   | No  |

## Reporting a Vulnerability

Report a suspected security vulnerability in private. Do not open a public
GitHub issue.

- Preferred: use [GitHub's private vulnerability reporting](https://github.com/McIndi/adapt/security/advisories/new)
  on this repository.
- Alternative: send an email to **security@mcindi.com** with a description
  of the issue, the steps to reproduce it, and its impact.

We acknowledge most reports within 5 business days. When a fix is ready, we
publish a patched release and, where appropriate, a GitHub Security
Advisory. Give us a reasonable window to ship a fix before you disclose the
issue in public.

## Scope

In scope: the `adapt` package as published on PyPI, its CLI, REST API, admin
UI, and MCP server. Out of scope: a vulnerability that needs an attacker to
already have superuser or admin access, or a vulnerability in a deployment
that runs without TLS after a clear warning to use it (see
`docs/manual/security.md`).

## Threat Model (first pass)

Adapt is a self-hosted server. It turns a directory of dataset files (CSV,
Excel, Parquet, Markdown, media, and more) into a CRUD API and an admin UI.
The operator controls the deployment. The main attacker of concern is one
of two kinds:

- An unauthenticated or under-privileged network client that tries to read
  or change data.
- An authenticated low-privilege user that tries to go beyond their
  granted permissions.

Uploads (`POST /api/uploads`) are off by default. When enabled, they
require `write` on the document root, reject path traversal, enforce a
size limit, and can sniff MIME types. See `docs/manual/security.md`.

Controls already in place (see `docs/manual/security.md` for detail):

- Session-cookie, API-key, and optional Keycloak Bearer authentication.
  API keys are stored as SHA-256 hashes. Passwords are hashed with
  PBKDF2-HMAC-SHA256 (100k iterations, per-user salt). OIDC JIT users
  get an unusable password hash.
- Resource-level authorization (`read`/`write`), enforced on every
  generated route. This includes MCP tool calls. Keycloak group names map
  onto existing Adapt groups. Adapt does not create groups from the token.
- CSRF protection for cookie-authenticated unsafe requests. API-key-only
  and Bearer-only requests without a session cookie are exempt.
- Security response headers (CSP, `X-Frame-Options`, HSTS when TLS is
  configured, and more) and `TrustedHostMiddleware`.
- An audit log for authentication events, admin actions, and dataset
  mutations.
- Per-resource locking and atomic file replacement. These reduce
  corruption and race conditions on concurrent writes.
- OIDC Bearer tokens must carry `aud` equal to Adapt `public_url` (or
  `oidc.audience`). Dynamic client registration is a Keycloak realm
  setting. Adapt is not an authorization server. JIT users get access
  only through Adapt groups whose names already exist.

Known, accepted gaps (tracked, not hidden):

- **Row-level write security**: `Plugin.filter_for_user()` filters reads.
  Dataset write paths do not yet enforce per-row authorization. See
  `docs/manual/known_limitations.md#write-level-row-security`. Until this
  gap closes, treat write access to a resource as all-or-nothing.
- **Secure transport is opt-in**: TLS, HSTS, and secure cookies activate
  only when you configure `--tls-cert`/`--tls-key`. For a non-local
  deployment, the operator must supply TLS, either directly or through a
  reverse proxy.
- **No SAST or secret-scanning in CI yet.** This is planned for a future
  milestone (see `MILESTONES.md`).

This note is a living document. When the attack surface changes, update it.
Do not wait until someone finds a vulnerability to update it.

## Supply Chain

- Runtime dependencies in `pyproject.toml` carry version limits (a lower
  bound plus an upper bound), instead of staying fully open-ended.
- Dependabot checks `pip`, GitHub Actions, and Docker every Monday
  (`.github/dependabot.yml`).
- The container `FROM` line keeps the `python:3.14-slim` tag and pins the
  multi-platform index digest. Refresh steps are in
  `docs/manual/container.md`.
- CI runs `pip-audit` against installed dependencies on every push and
  every pull request (`.github/workflows/test.yml`, `dependency-audit`
  job).
- Releases publish to PyPI through OIDC trusted publishing
  (`.github/workflows/publish-pypi.yml`). This repository stores no
  long-lived PyPI token.
- Artifact signing and SBOM (Software Bill of Materials) generation are
  not yet in place. These remain milestone M3 Phase 3 (see
  `MILESTONES.md`).
