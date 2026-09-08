"""OIDC resource-server and browser SSO tests. Uses a local RSA key, not Keycloak."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlmodel import Session, select

from adapt.api_keys import create_api_key_record
from adapt.app import create_app
from adapt.auth.dependencies import get_current_user
from adapt.auth.oidc import (
    OIDC_STATE_COOKIE,
    OIDC_VERIFIER_COOKIE,
    clear_oidc_caches,
    sync_oidc_user,
)
from adapt.auth.password import hash_password, unusable_password_hash, verify_password
from adapt.auth.session import create_session
from adapt.config import AdaptConfig
from adapt.security import CSRF_COOKIE_NAME, generate_csrf_token, requires_csrf_validation
from adapt.storage import DBSession, Group, User, UserGroup, init_database

ISSUER = "https://keycloak.example.com/realms/prod"
PUBLIC_URL = "https://adapt.example.com"
CLIENT_ID = "adapt-web"


@pytest.fixture
def rsa_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = "test-key"
    return private_key, {"keys": [jwk]}


@pytest.fixture
def oidc_config(tmp_path):
    config = AdaptConfig(root=tmp_path)
    config.mcp_enabled = True
    config.oidc.update({
        "issuer": ISSUER,
        "client_id": CLIENT_ID,
        "client_secret": "web-secret",
        "public_url": PUBLIC_URL,
        "audience": PUBLIC_URL,
        "local_login": True,
    })
    return config


@pytest.fixture(autouse=True)
def _clear_oidc_cache():
    clear_oidc_caches()
    yield
    clear_oidc_caches()


def _mint(private_key, claims, *, expired=False, audience=PUBLIC_URL):
    now = datetime.now(tz=timezone.utc)
    payload = {
        "iss": ISSUER,
        "aud": audience,
        "exp": now + timedelta(hours=1),
        "iat": now,
        "preferred_username": "alice",
        "groups": ["/products_readonly"],
        "realm_access": {"roles": []},
    }
    payload.update(claims)
    if expired:
        payload["exp"] = now - timedelta(minutes=5)
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key"})


def _patch_jwks(monkeypatch, jwks):
    monkeypatch.setattr("adapt.auth.oidc.fetch_jwks", lambda config: jwks)
    monkeypatch.setattr(
        "adapt.auth.oidc.fetch_oidc_metadata",
        lambda config: {
            "issuer": ISSUER,
            "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
            "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
            "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
            "end_session_endpoint": f"{ISSUER}/protocol/openid-connect/logout",
        },
    )


def _request(app, headers=None, cookies=None):
    request = MagicMock()
    request.app.state.db_engine = app.state.db_engine
    request.app.state.config = app.state.config
    request.headers = headers or {}
    request.cookies = cookies or {}
    return request


def test_jwt_success_creates_user(tmp_path, rsa_pair, oidc_config, monkeypatch):
    private_key, jwks = rsa_pair
    _patch_jwks(monkeypatch, jwks)
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        db.add(Group(name="products_readonly"))
        db.commit()
    app = create_app(oidc_config)
    token = _mint(private_key, {})
    user = get_current_user(_request(app, headers={"authorization": f"Bearer {token}"}))
    assert user is not None
    assert user.username == "alice"
    assert verify_password("anything", user.password_hash) is False
    with Session(engine) as db:
        memberships = db.exec(select(UserGroup).where(UserGroup.user_id == user.id)).all()
        assert len(memberships) == 1
        assert memberships[0].oidc_managed is True


def test_jwt_bad_audience_rejected(tmp_path, rsa_pair, oidc_config, monkeypatch):
    private_key, jwks = rsa_pair
    _patch_jwks(monkeypatch, jwks)
    init_database(oidc_config.db_path)
    app = create_app(oidc_config)
    token = _mint(private_key, {}, audience="https://other.example")
    assert get_current_user(_request(app, headers={"authorization": f"Bearer {token}"})) is None


def test_jwt_expired_rejected(tmp_path, rsa_pair, oidc_config, monkeypatch):
    private_key, jwks = rsa_pair
    _patch_jwks(monkeypatch, jwks)
    init_database(oidc_config.db_path)
    app = create_app(oidc_config)
    token = _mint(private_key, {}, expired=True)
    assert get_current_user(_request(app, headers={"authorization": f"Bearer {token}"})) is None


def test_jwt_inactive_user_rejected(tmp_path, rsa_pair, oidc_config, monkeypatch):
    private_key, jwks = rsa_pair
    _patch_jwks(monkeypatch, jwks)
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        db.add(User(username="alice", password_hash=unusable_password_hash(), is_active=False))
        db.commit()
    app = create_app(oidc_config)
    token = _mint(private_key, {})
    assert get_current_user(_request(app, headers={"authorization": f"Bearer {token}"})) is None


def test_group_sync_oidc_managed_vs_manual(tmp_path, oidc_config):
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        keep = Group(name="products_readonly")
        drop = Group(name="orders_readonly")
        extra = Group(name="manual_only")
        db.add(keep)
        db.add(drop)
        db.add(extra)
        db.commit()
        db.refresh(keep)
        db.refresh(drop)
        db.refresh(extra)
        user = User(username="alice", password_hash=unusable_password_hash(), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(UserGroup(user_id=user.id, group_id=keep.id, oidc_managed=True))
        db.add(UserGroup(user_id=user.id, group_id=drop.id, oidc_managed=True))
        db.add(UserGroup(user_id=user.id, group_id=extra.id, oidc_managed=False))
        db.commit()
        user = sync_oidc_user(db, oidc_config, {
            "preferred_username": "alice",
            "groups": ["/products_readonly"],
            "realm_access": {"roles": ["adapt-admin"]},
        })
        assert user.is_superuser is True
        names = {
            db.get(Group, row.group_id).name: row.oidc_managed
            for row in db.exec(select(UserGroup).where(UserGroup.user_id == user.id)).all()
        }
        assert names["products_readonly"] is True
        assert names["manual_only"] is False
        assert "orders_readonly" not in names


def test_unknown_keycloak_group_is_ignored(tmp_path, oidc_config):
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        user = sync_oidc_user(db, oidc_config, {
            "preferred_username": "bob",
            "groups": ["/does_not_exist"],
        })
        assert user is not None
        assert db.exec(select(UserGroup).where(UserGroup.user_id == user.id)).all() == []


def test_mcp_unauthenticated_returns_prm_challenge(tmp_path, oidc_config):
    init_database(oidc_config.db_path)
    client = TestClient(create_app(oidc_config))
    response = client.post("/mcp/")
    assert response.status_code == 401
    header = response.headers.get("www-authenticate", "")
    assert 'realm="adapt"' in header
    assert f'{PUBLIC_URL}/.well-known/oauth-protected-resource/mcp' in header


def test_mcp_api_key_still_passes_oidc_challenge(tmp_path, oidc_config):
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        user = User(username="agent", password_hash=hash_password("x"), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        raw_key, _ = create_api_key_record(db, user.id, "mcp", None)
    client = TestClient(create_app(oidc_config))
    with client:
        response = client.post("/mcp/", headers={"X-API-Key": raw_key})
    assert response.status_code != 401


def test_prm_document_shape(tmp_path, oidc_config):
    init_database(oidc_config.db_path)
    client = TestClient(create_app(oidc_config))
    for path in (
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
    ):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["resource"] == f"{PUBLIC_URL}/mcp"
        assert body["authorization_servers"] == [ISSUER]
        assert body["bearer_methods_supported"] == ["header"]
        assert "openid" in body["scopes_supported"]


def test_prm_absent_when_oidc_off(tmp_path):
    config = AdaptConfig(root=tmp_path)
    init_database(config.db_path)
    client = TestClient(create_app(config))
    assert client.get("/.well-known/oauth-protected-resource").status_code == 404
    assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 404
    with client:
        response = client.post("/mcp/")
    authenticate = response.headers.get("www-authenticate") or ""
    assert "resource_metadata" not in authenticate


def test_oidc_login_redirect(tmp_path, oidc_config, monkeypatch):
    _patch_jwks(monkeypatch, {"keys": []})
    init_database(oidc_config.db_path)
    client = TestClient(create_app(oidc_config))
    response = client.get("/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    assert location.netloc == "keycloak.example.com"
    query = parse_qs(location.query)
    assert query["client_id"] == [CLIENT_ID]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [f"{PUBLIC_URL}/auth/oidc/callback"]
    assert OIDC_STATE_COOKIE in response.cookies
    assert OIDC_VERIFIER_COOKIE in response.cookies


def test_oidc_callback_sets_session(tmp_path, rsa_pair, oidc_config, monkeypatch):
    private_key, jwks = rsa_pair
    _patch_jwks(monkeypatch, jwks)
    access = _mint(private_key, {})
    id_token = "id-token-value"

    def fake_exchange(config, code, verifier):
        assert code == "auth-code"
        assert verifier == "pkce-verifier"
        return {"access_token": access, "id_token": id_token}

    monkeypatch.setattr("adapt.auth.routes.exchange_code", fake_exchange)
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        db.add(Group(name="products_readonly"))
        db.commit()
    client = TestClient(create_app(oidc_config))
    client.cookies.set(OIDC_STATE_COOKIE, "abc")
    client.cookies.set(OIDC_VERIFIER_COOKIE, "pkce-verifier")
    response = client.get(
        "/auth/oidc/callback?code=auth-code&state=abc",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert client.cookies.get("adapt_session")
    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == "alice")).one()
        session = db.exec(select(DBSession).where(DBSession.user_id == user.id)).one()
        assert session.id_token == id_token


def test_local_password_login_still_works(tmp_path, oidc_config):
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        db.add(User(username="local", password_hash=hash_password("Local!Secure-Phrase1"), is_active=True))
        db.commit()
    client = TestClient(create_app(oidc_config))
    response = client.post("/auth/login", data={"username": "local", "password": "Local!Secure-Phrase1"})
    assert response.status_code == 200
    html = client.get("/auth/login")
    assert "Sign in with Keycloak" in html.text
    assert 'id="login-form"' in html.text


def test_local_login_disabled(tmp_path, oidc_config):
    oidc_config.oidc["local_login"] = False
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        db.add(User(username="local", password_hash=hash_password("Local!Secure-Phrase1"), is_active=True))
        db.commit()
    client = TestClient(create_app(oidc_config))
    response = client.post("/auth/login", data={"username": "local", "password": "Local!Secure-Phrase1"})
    assert response.status_code == 403
    html = client.get("/auth/login")
    assert "Sign in with Keycloak" in html.text
    assert 'id="login-form"' not in html.text


def test_csrf_bearer_only_post_is_exempt():
    request = MagicMock()
    request.method = "POST"
    request.cookies = {}
    request.headers = {"authorization": "Bearer abc"}
    assert requires_csrf_validation(request) is False


def test_csrf_session_plus_bearer_still_required(tmp_path):
    config = AdaptConfig(root=tmp_path)
    engine = init_database(config.db_path)
    with Session(engine) as db:
        user = User(username="sess", password_hash=hash_password("x"), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    client = TestClient(create_app(config))
    client.cookies.set("adapt_session", token)
    client.cookies.pop(CSRF_COOKIE_NAME, None)
    response = client.put(
        "/auth/password",
        json={"current_password": "x", "new_password": "New!Secure-Phrase2"},
        headers={"Authorization": "Bearer ignore-me"},
    )
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


def test_sqlite_schema_patch_adds_columns(tmp_path):
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE usergroup (user_id INTEGER, group_id INTEGER, PRIMARY KEY (user_id, group_id))")
    conn.execute(
        "CREATE TABLE dbsession (id INTEGER PRIMARY KEY, user_id INTEGER, token TEXT, "
        "created_at TEXT, expires_at TEXT, last_active TEXT)"
    )
    conn.commit()
    conn.close()
    engine = init_database(db_path)
    with engine.connect() as connection:
        usergroup = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(usergroup)")}
        sessions = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(dbsession)")}
    assert "oidc_managed" in usergroup
    assert "id_token" in sessions


def test_logout_redirects_to_keycloak(tmp_path, oidc_config, monkeypatch):
    _patch_jwks(monkeypatch, {"keys": []})
    engine = init_database(oidc_config.db_path)
    with Session(engine) as db:
        user = User(username="alice", password_hash=unusable_password_hash(), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id, id_token="id-token-hint")
    client = TestClient(create_app(oidc_config))
    client.cookies.set("adapt_session", token)
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())
    response = client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "protocol/openid-connect/logout" in response.headers["location"]
    assert "id_token_hint" in response.headers["location"]
