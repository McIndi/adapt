from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit


def is_safe_next_path(value: str | None) -> bool:
    if not value:
        return False

    candidate = unquote(value).strip()
    if not candidate:
        return False

    if candidate.startswith("//"):
        return False

    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return False

    return candidate.startswith("/")


def normalize_next_path(value: str | None, fallback: str = "/") -> str:
    if not is_safe_next_path(value):
        return fallback
    return unquote(value).strip()


def login_redirect_url(next_path: str | None = None, fallback: str = "/") -> str:
    safe_next = normalize_next_path(next_path, fallback=fallback)
    return f"/auth/login?next={quote(safe_next, safe='/')}"
