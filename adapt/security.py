from __future__ import annotations

import secrets
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse


CSRF_COOKIE_NAME = "adapt_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_FORM_FIELD = "csrf_token"
SESSION_COOKIE_NAME = "adapt_session"
API_KEY_HEADER = "X-API-Key"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def build_allowed_hosts(config_host: str) -> list[str]:
    if config_host in {"0.0.0.0", "::", ""}:
        return ["*"]
    return [config_host, "localhost", "127.0.0.1", "testserver"]


def requires_csrf_validation(request: Request) -> bool:
    if request.method.upper() in SAFE_METHODS:
        return False

    has_session_cookie = bool(request.cookies.get(SESSION_COOKIE_NAME))
    has_api_key_header = bool(request.headers.get(API_KEY_HEADER))

    if has_api_key_header and not has_session_cookie:
        return False

    return has_session_cookie


async def validate_csrf(request: Request) -> JSONResponse | None:
    if not requires_csrf_validation(request):
        return None

    expected = request.cookies.get(CSRF_COOKIE_NAME)
    if not expected:
        return JSONResponse(status_code=403, content={"detail": "Missing CSRF cookie"})

    provided = request.headers.get(CSRF_HEADER_NAME)
    if not provided:
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            provided = form.get(CSRF_FORM_FIELD)

    if not provided:
        return JSONResponse(status_code=403, content={"detail": "Missing CSRF token"})

    if not secrets.compare_digest(str(provided), str(expected)):
        return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})

    return None


def apply_security_headers(response, use_tls: bool) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers[
        "Content-Security-Policy"
    ] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com https://cdn.datatables.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.datatables.net; "
        "font-src 'self'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    if use_tls:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"


def set_csrf_cookie(response, token: str, secure: bool) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )
