"""Keycloak OIDC helpers: discovery, JWT validation, JIT user and group sync."""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import threading
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWK
from sqlmodel import Session, select

from ..config import AdaptConfig
from ..storage import Group, User, UserGroup
from .password import unusable_password_hash

logger = logging.getLogger(__name__)

OIDC_STATE_COOKIE = "adapt_oidc_state"
OIDC_VERIFIER_COOKIE = "adapt_oidc_verifier"
OIDC_NEXT_COOKIE = "adapt_oidc_next"
OIDC_COOKIE_MAX_AGE = 600
HTTP_TIMEOUT = 10.0
METADATA_TTL_SECONDS = 3600

_cache_lock = threading.Lock()
_metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def normalize_group_name(raw: str) -> str:
    """Strip a leading Keycloak path prefix such as `/products_readonly`."""
    name = raw.strip()
    if name.startswith("/"):
        name = name.lstrip("/")
    return name


def token_group_names(claims: dict[str, Any], config: AdaptConfig) -> set[str]:
    groups_claim = str(config.oidc.get("groups_claim") or "groups")
    names: set[str] = set()
    raw_groups = claims.get(groups_claim) or []
    if isinstance(raw_groups, str):
        raw_groups = [raw_groups]
    if isinstance(raw_groups, list):
        for item in raw_groups:
            if isinstance(item, str) and item.strip():
                names.add(normalize_group_name(item))
    realm_access = claims.get("realm_access") or {}
    roles = realm_access.get("roles") if isinstance(realm_access, dict) else None
    if isinstance(roles, list):
        for item in roles:
            if isinstance(item, str) and item.strip():
                names.add(item.strip())
    return names


def superuser_from_claims(claims: dict[str, Any], config: AdaptConfig) -> bool:
    configured = {role.strip() for role in config.oidc.get("superuser_roles") or [] if role.strip()}
    if not configured:
        return False
    return bool(configured & token_group_names(claims, config))


def username_from_claims(claims: dict[str, Any], config: AdaptConfig) -> str | None:
    claim = str(config.oidc.get("username_claim") or "preferred_username")
    value = claims.get(claim)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def sync_oidc_user(db: Session, config: AdaptConfig, claims: dict[str, Any]) -> User | None:
    """Create or update the Adapt user for a validated token. Returns None if inactive."""
    username = username_from_claims(claims, config)
    if not username:
        logger.warning("OIDC token missing username claim")
        return None

    user = db.exec(select(User).where(User.username == username)).first()
    if user is None:
        user = User(
            username=username,
            password_hash=unusable_password_hash(),
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created OIDC user %s", username)

    if not user.is_active:
        logger.warning("OIDC authentication rejected for inactive user %s", username)
        return None

    user.is_superuser = superuser_from_claims(claims, config)
    db.add(user)

    wanted = token_group_names(claims, config)
    groups = {group.name: group for group in db.exec(select(Group)).all()}
    memberships = db.exec(select(UserGroup).where(UserGroup.user_id == user.id)).all()
    by_group_id = {row.group_id: row for row in memberships}

    for name, group in groups.items():
        if name not in wanted:
            continue
        existing = by_group_id.get(group.id)
        if existing is None:
            db.add(UserGroup(user_id=user.id, group_id=group.id, oidc_managed=True))

    for row in memberships:
        group = db.get(Group, row.group_id)
        if group is None:
            continue
        if row.oidc_managed and group.name not in wanted:
            db.delete(row)

    db.commit()
    db.refresh(user)
    return user


def _get_cached(cache: dict[str, tuple[float, dict[str, Any]]], key: str) -> dict[str, Any] | None:
    entry = cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at < time.monotonic():
        cache.pop(key, None)
        return None
    return value


def fetch_oidc_metadata(config: AdaptConfig) -> dict[str, Any]:
    issuer = config.oidc_issuer()
    with _cache_lock:
        cached = _get_cached(_metadata_cache, issuer)
        if cached is not None:
            return cached
    url = f"{issuer}/.well-known/openid-configuration"
    response = httpx.get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    metadata = response.json()
    with _cache_lock:
        _metadata_cache[issuer] = (time.monotonic() + METADATA_TTL_SECONDS, metadata)
    return metadata


def fetch_jwks(config: AdaptConfig) -> dict[str, Any]:
    metadata = fetch_oidc_metadata(config)
    jwks_uri = metadata.get("jwks_uri")
    if not jwks_uri:
        raise ValueError("OIDC metadata is missing jwks_uri")
    with _cache_lock:
        cached = _get_cached(_jwks_cache, jwks_uri)
        if cached is not None:
            return cached
    response = httpx.get(jwks_uri, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    jwks = response.json()
    with _cache_lock:
        _jwks_cache[jwks_uri] = (time.monotonic() + METADATA_TTL_SECONDS, jwks)
    return jwks


def clear_oidc_caches() -> None:
    with _cache_lock:
        _metadata_cache.clear()
        _jwks_cache.clear()


def validate_access_token(config: AdaptConfig, token: str) -> dict[str, Any] | None:
    """Validate an RS* JWT (iss, aud, exp, signature). Returns claims or None."""
    audience = config.oidc_audience()
    issuer = config.oidc_issuer()
    if not audience or not issuer:
        logger.error("OIDC is enabled but audience/public_url or issuer is missing")
        return None
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        jwks = fetch_jwks(config)
        keys = jwks.get("keys") or []
        matching = None
        for key in keys:
            if kid is None or key.get("kid") == kid:
                matching = key
                break
        if matching is None:
            logger.warning("No matching JWKS key for token")
            return None
        public_key = PyJWK.from_dict(matching).key
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256", "RS384", "RS512"],
            issuer=issuer,
            audience=audience,
            leeway=30,
            options={"require": ["exp", "iss", "aud"]},
        )
    except Exception:
        logger.debug("Bearer JWT validation failed", exc_info=True)
        return None


def authenticate_bearer(db: Session, config: AdaptConfig, token: str) -> User | None:
    claims = validate_access_token(config, token)
    if claims is None:
        return None
    return sync_oidc_user(db, config, claims)


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorization_redirect_url(config: AdaptConfig, state: str, challenge: str) -> str:
    metadata = fetch_oidc_metadata(config)
    endpoint = metadata.get("authorization_endpoint")
    if not endpoint:
        raise ValueError("OIDC metadata is missing authorization_endpoint")
    public_url = config.oidc_public_url()
    scopes = str(config.oidc.get("scopes") or "openid profile")
    query = urlencode({
        "response_type": "code",
        "client_id": config.oidc.get("client_id"),
        "redirect_uri": f"{public_url}/auth/oidc/callback",
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"{endpoint}?{query}"


def exchange_code(config: AdaptConfig, code: str, verifier: str) -> dict[str, Any]:
    metadata = fetch_oidc_metadata(config)
    token_endpoint = metadata.get("token_endpoint")
    if not token_endpoint:
        raise ValueError("OIDC metadata is missing token_endpoint")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"{config.oidc_public_url()}/auth/oidc/callback",
        "client_id": config.oidc.get("client_id"),
        "code_verifier": verifier,
    }
    secret = config.oidc.get("client_secret") or ""
    auth = None
    if secret:
        auth = (str(config.oidc.get("client_id")), str(secret))
    response = httpx.post(token_endpoint, data=data, auth=auth, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def end_session_url(config: AdaptConfig, id_token: str) -> str | None:
    try:
        metadata = fetch_oidc_metadata(config)
    except Exception:
        logger.debug("Failed to load OIDC metadata for logout", exc_info=True)
        return None
    endpoint = metadata.get("end_session_endpoint")
    if not endpoint:
        return None
    query = urlencode({
        "id_token_hint": id_token,
        "post_logout_redirect_uri": f"{config.oidc_public_url()}/auth/login",
    })
    return f"{endpoint}?{query}"


def protected_resource_metadata(config: AdaptConfig) -> dict[str, Any]:
    public_url = config.oidc_public_url()
    scopes = [item for item in str(config.oidc.get("scopes") or "").split() if item]
    return {
        "resource": f"{public_url}/mcp",
        "authorization_servers": [config.oidc_issuer()],
        "bearer_methods_supported": ["header"],
        "scopes_supported": scopes,
    }


def www_authenticate_header(config: AdaptConfig) -> str:
    metadata_url = f"{config.oidc_public_url()}/.well-known/oauth-protected-resource/mcp"
    return f'Bearer realm="adapt", resource_metadata="{metadata_url}"'


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, remainder = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = remainder.strip()
    return token or None
