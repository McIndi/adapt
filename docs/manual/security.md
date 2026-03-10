# Security

[Previous](admin_guide) | [Next](configuration) | [Index](index)

This guide documents security behavior currently implemented in Adapt.

## Authentication

Adapt supports:

1. Session cookie authentication (`adapt_session`)
2. API key authentication (`X-API-Key`)

Login/logout routes:

- `GET /auth/login`
- `POST /auth/login`
- `POST /auth/logout`

Session behavior:

- Session TTL is 7 days
- Sliding renewal on valid session usage
- Expired sessions are cleaned by a background task

API key behavior:

- Keys are stored as SHA-256 hashes
- Keys can be inactive or expired
- `last_used_at` is updated on successful key usage

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

## CSRF Protection

CSRF is enforced for unsafe HTTP methods when session cookies are involved.

Key points:

- CSRF cookie name: `adapt_csrf`
- CSRF header name: `X-CSRF-Token`
- Form field fallback: `csrf_token`
- API-key-only requests without session cookies are exempt
- If both session and API key are present, CSRF still applies

## Security Headers

Adapt sets security headers on responses:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy: ...` (policy configured in code)
- `Strict-Transport-Security` when TLS is enabled

## Host Header Protection

Adapt uses `TrustedHostMiddleware` with allowed hosts derived from configured host.

## TLS and Cookies

When TLS cert and key are configured together:

- HTTPS is enabled
- HSTS is enabled
- Secure-cookie behavior is enabled by server configuration

## Locking and Safe Writes

Dataset write paths use lock management and atomic replacement to reduce corruption and race risks.

Lock behavior includes:

- Per-resource lock records
- Retry with exponential backoff
- Timeout-based acquisition failure
- Stale lock cleanup

## Audit and Admin Security Endpoints

Superuser endpoints include:

- `/admin/users`
- `/admin/groups`
- `/admin/permissions`
- `/admin/locks`
- `/admin/cache`
- `/admin/api-keys`
- `/admin/audit-logs`

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
- Rotate API keys and deactivate unused keys.
- Keep superuser accounts limited and monitored.
- Review audit logs regularly.

[Previous](admin_guide) | [Next](configuration) | [Index](index)
