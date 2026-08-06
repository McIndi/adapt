# Security Policy

## Supported Versions

Adapt is pre-1.0 (currently `0.3.x`). Only the latest published release on
PyPI is supported with security fixes. There is no LTS branch yet.

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes |
| < 0.3   | No  |

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately — do not open a
public GitHub issue.

- Preferred: use [GitHub's private vulnerability reporting](https://github.com/McIndi/adapt/security/advisories/new)
  on this repository.
- Alternative: email **security@mcindi.com** with a description of the
  issue, steps to reproduce, and its impact.

We aim to acknowledge reports within 5 business days. Once a fix is ready,
we will publish a patched release and, where appropriate, a GitHub Security
Advisory. Please give us a reasonable window to ship a fix before any public
disclosure.

## Scope

In scope: the `adapt` package as published on PyPI, its CLI, REST API, admin
UI, and MCP server. Out of scope: vulnerabilities that require an attacker
to already have superuser/admin access, or that depend on a deployment
running without TLS after being explicitly warned to use it (see
`docs/manual/security.md`).

## Threat Model (first pass)

Adapt is a self-hosted server that turns a directory of dataset files (CSV,
Excel, Parquet, Markdown, media, etc.) into a CRUD API and admin UI. The
operator controls the deployment; the primary attacker of concern is an
unauthenticated or under-privileged network client attempting to read or
modify data, or an authenticated low-privilege user attempting to exceed
their granted permissions.

Controls already in place (see `docs/manual/security.md` for detail):

- Session-cookie and API-key authentication, with API keys stored as
  SHA-256 hashes and passwords hashed with PBKDF2-HMAC-SHA256 (100k
  iterations, per-user salt).
- Resource-level authorization (`read`/`write`) enforced on every generated
  route, including MCP tool calls.
- CSRF protection for cookie-authenticated unsafe requests.
- Security response headers (CSP, `X-Frame-Options`, HSTS when TLS is
  configured, etc.) and `TrustedHostMiddleware`.
- An audit log for authentication events, admin actions, and dataset
  mutations.
- Per-resource locking and atomic file replacement to reduce corruption
  and race conditions on concurrent writes.

Known, accepted gaps (tracked, not hidden):

- **Row-level write security**: `Plugin.filter_for_user()` filters reads,
  but dataset write paths do not currently enforce per-row authorization.
  See `docs/manual/known_limitations.md#write-level-row-security`. Treat
  write access to a resource as all-or-nothing until this is closed.
- **Secure transport is opt-in**: TLS/HSTS/secure cookies only activate
  when `--tls-cert`/`--tls-key` are configured. Operators must supply TLS
  themselves (directly or via a reverse proxy) for any non-local
  deployment.
- **No SAST or secret-scanning in CI yet.** Planned for a future
  milestone (see `MILESTONES.md`).

This note is a living document — update it when the attack surface changes,
not just when a vulnerability is found.

## Supply Chain

- Runtime dependencies in `pyproject.toml` are version-constrained (lower
  bound plus an upper bound) rather than left fully open-ended.
- CI runs `pip-audit` against installed dependencies on every push and pull
  request (`.github/workflows/test.yml`, `dependency-audit` job).
- Releases are published to PyPI via OIDC trusted publishing
  (`.github/workflows/publish-pypi.yml`); no long-lived PyPI token is
  stored in this repository.
- Artifact signing and SBOM generation are not yet in place — planned for
  milestone M2 (see `MILESTONES.md`).
