from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from adapt.api_keys import create_api_key_record
from adapt.app import create_app
from adapt.auth.password import hash_password
from adapt.config import AdaptConfig
from adapt.permissions import PermissionChecker
from adapt.security import CSRF_COOKIE_NAME, generate_csrf_token
from adapt.storage import Action, AuditLog, Group, GroupPermission, Permission, User, UserGroup


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200
    client.cookies.update(response.cookies)


def _make_user(app, username: str, *, write_root: bool) -> tuple[int, str]:
    with Session(app.state.db_engine) as db:
        user = User(username=username, password_hash=hash_password("password"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)

        if write_root:
            perm = Permission(resource="", action=Action.write, description="Write document root")
            db.add(perm)
            db.commit()
            db.refresh(perm)

            group = Group(name=f"{username}_root_writers", description="Root upload writers")
            db.add(group)
            db.commit()
            db.refresh(group)

            db.add(UserGroup(user_id=user.id, group_id=group.id))
            db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
            db.commit()

        return user.id, user.username


@pytest.fixture
def enabled_app(tmp_path):
    config = AdaptConfig(root=tmp_path)
    config.upload["enabled"] = True
    config.mcp_enabled = False
    app = create_app(config)

    with Session(app.state.db_engine) as db:
        admin = User(username="admin", password_hash=hash_password("admin"), is_superuser=True)
        db.add(admin)
        db.commit()

    return app


@pytest.fixture
def enabled_client(enabled_app):
    client = TestClient(enabled_app)
    csrf = generate_csrf_token()
    client.cookies.set(CSRF_COOKIE_NAME, csrf)
    return client


def test_upload_create_registers_resource_and_grants_owner(enabled_client, enabled_app):
    user_id, username = _make_user(enabled_app, "uploader", write_root=True)
    _login(enabled_client, username, "password")

    response = enabled_client.post(
        "/api/uploads",
        data={"filename": "notes.txt"},
        files={"file": ("notes.txt", b"alpha\nbeta\n", "text/plain")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["path"] == "notes.txt"
    assert body["operation"] == "created"

    assert (enabled_app.state.config.root / "notes.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"

    with Session(enabled_app.state.db_engine) as db:
        checker = PermissionChecker(db)
        user = db.get(User, user_id)
        assert user is not None
        assert checker.has_permission(user, "notes", "read") is True
        assert checker.has_permission(user, "notes", "write") is True

        success = db.exec(select(AuditLog).where(AuditLog.action == "upload_success")).first()
        assert success is not None
        assert success.user_id == user.id
        assert success.resource == "notes.txt"

    readback = enabled_client.get("/notes")
    assert readback.status_code == 200
    assert "alpha" in readback.text

    search = enabled_client.get("/search", params={"q": "beta"})
    assert search.status_code == 200
    assert search.json()["count"] == 1


def test_upload_overwrite_records_new_audit_entry(enabled_client, enabled_app):
    _, username = _make_user(enabled_app, "uploader2", write_root=True)
    _login(enabled_client, username, "password")

    first = enabled_client.post(
        "/api/uploads",
        data={"filename": "overwrite.txt"},
        files={"file": ("overwrite.txt", b"one", "text/plain")},
    )
    assert first.status_code == 201

    second = enabled_client.post(
        "/api/uploads",
        data={"filename": "overwrite.txt"},
        files={"file": ("overwrite.txt", b"two", "text/plain")},
    )
    assert second.status_code == 201
    assert second.json()["operation"] == "overwritten"

    with Session(enabled_app.state.db_engine) as db:
        audits = db.exec(select(AuditLog).where(AuditLog.action == "upload_success").order_by(AuditLog.timestamp.asc())).all()
        assert len(audits) == 2
        assert audits[-1].details and "overwritten" in audits[-1].details

    assert (enabled_app.state.config.root / "overwrite.txt").read_text(encoding="utf-8") == "two"


def test_upload_rejects_traversal_and_symlink_escape(enabled_client, enabled_app):
    _, username = _make_user(enabled_app, "uploader3", write_root=True)
    _login(enabled_client, username, "password")

    traversal = enabled_client.post(
        "/api/uploads",
        data={"filename": "../evil.txt"},
        files={"file": ("evil.txt", b"bad", "text/plain")},
    )
    assert traversal.status_code == 400

    outside = enabled_app.state.config.root.parent / "outside.txt"
    outside.write_text("escape", encoding="utf-8")
    link = enabled_app.state.config.root / "linked.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available in this test environment")

    symlink = enabled_client.post(
        "/api/uploads",
        data={"filename": "linked.txt"},
        files={"file": ("linked.txt", b"bad", "text/plain")},
    )
    assert symlink.status_code == 400


def test_upload_blocks_readonly_and_unauthorized_users(tmp_path):
    readonly_config = AdaptConfig(root=tmp_path, readonly=True)
    readonly_config.upload["enabled"] = True
    readonly_app = create_app(readonly_config)
    with Session(readonly_app.state.db_engine) as db:
        user = User(username="readonly", password_hash=hash_password("password"), is_superuser=False)
        db.add(user)
        db.commit()

        perm = Permission(resource="", action=Action.write)
        db.add(perm)
        db.commit()
        db.refresh(perm)
        group = Group(name="readonly_root_writers")
        db.add(group)
        db.commit()
        db.refresh(group)
        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
        db.commit()

    client = TestClient(readonly_app)
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())
    _login(client, "readonly", "password")

    readonly_response = client.post(
        "/api/uploads",
        data={"filename": "readonly.txt"},
        files={"file": ("readonly.txt", b"blocked", "text/plain")},
    )
    assert readonly_response.status_code == 405

    disabled_app = create_app(AdaptConfig(root=tmp_path / "disabled"))
    with Session(disabled_app.state.db_engine) as db:
        user = User(username="disabled", password_hash=hash_password("password"), is_superuser=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        perm = Permission(resource="", action=Action.write)
        db.add(perm)
        db.commit()
        db.refresh(perm)
        group = Group(name="disabled_root_writers")
        db.add(group)
        db.commit()
        db.refresh(group)
        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
        db.commit()

    disabled_client = TestClient(disabled_app)
    disabled_client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())
    _login(disabled_client, "disabled", "password")

    disabled_response = disabled_client.post(
        "/api/uploads",
        data={"filename": "disabled.txt"},
        files={"file": ("disabled.txt", b"blocked", "text/plain")},
    )
    assert disabled_response.status_code == 403


def test_upload_requires_root_write_permission(enabled_client, enabled_app):
    _, username = _make_user(enabled_app, "noaccess", write_root=False)
    _login(enabled_client, username, "password")

    response = enabled_client.post(
        "/api/uploads",
        data={"filename": "denied.txt"},
        files={"file": ("denied.txt", b"blocked", "text/plain")},
    )
    assert response.status_code == 403


def test_upload_permission_grant_via_admin_api_enables_regular_user(enabled_client, enabled_app):
    _login(enabled_client, "admin", "admin")

    created_user = enabled_client.post(
        "/admin/users",
        json={"username": "delegated", "password": "password", "is_superuser": False},
    )
    assert created_user.status_code == 200
    user_id = created_user.json()["id"]

    created_group = enabled_client.post(
        "/admin/groups",
        json={"name": "upload-writers", "description": "Can upload to document root"},
    )
    assert created_group.status_code == 200
    group_id = created_group.json()["id"]

    created_perm = enabled_client.post(
        "/admin/permissions",
        json={"resource": "__root__", "action": "write", "description": "Root upload write"},
    )
    assert created_perm.status_code == 200
    perm_id = created_perm.json()["id"]

    attach_perm = enabled_client.post(f"/admin/groups/{group_id}/permissions/{perm_id}")
    assert attach_perm.status_code == 200

    attach_user = enabled_client.post(f"/admin/groups/{group_id}/users/{user_id}")
    assert attach_user.status_code == 200

    _login(enabled_client, "delegated", "password")
    response = enabled_client.post(
        "/api/uploads",
        data={"filename": "delegated.txt"},
        files={"file": ("delegated.txt", b"delegated upload", "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["operation"] == "created"


def test_upload_rejects_mime_mismatch_when_strict(enabled_client, enabled_app):
    enabled_app.state.config.upload["strict_mime_sniffing"] = True
    enabled_app.state.config.upload["allowed_mime_types"] = ["image/png"]

    _, username = _make_user(enabled_app, "strictmime", write_root=True)
    _login(enabled_client, username, "password")

    response = enabled_client.post(
        "/api/uploads",
        data={"filename": "image.png"},
        files={"file": ("image.png", b"this is not png", "image/png")},
    )
    assert response.status_code == 400


def test_upload_collision_policy_reject_disables_overwrite(enabled_client, enabled_app):
    enabled_app.state.config.upload["collision_policy"] = "reject"

    _, username = _make_user(enabled_app, "collider", write_root=True)
    _login(enabled_client, username, "password")

    first = enabled_client.post(
        "/api/uploads",
        data={"filename": "collision.txt"},
        files={"file": ("collision.txt", b"first", "text/plain")},
    )
    assert first.status_code == 201

    second = enabled_client.post(
        "/api/uploads",
        data={"filename": "collision.txt"},
        files={"file": ("collision.txt", b"second", "text/plain")},
    )
    assert second.status_code == 409


def test_upload_enforces_large_file_limit(enabled_client, enabled_app):
    enabled_app.state.config.upload["max_size_bytes"] = 1024

    _, username = _make_user(enabled_app, "largelimit", write_root=True)
    _login(enabled_client, username, "password")

    payload = b"a" * 2048
    response = enabled_client.post(
        "/api/uploads",
        data={"filename": "too-large.txt"},
        files={"file": ("too-large.txt", payload, "text/plain")},
    )
    assert response.status_code == 413


def test_upload_concurrent_overwrite_is_atomic_and_audited(enabled_app):
    user_id, username = _make_user(enabled_app, "parallel", write_root=True)

    with Session(enabled_app.state.db_engine) as db:
        raw_key, _ = create_api_key_record(db, user_id, "concurrent upload test", None)

    filename = "parallel.txt"
    payloads = [
        b"payload-a",
        b"payload-b",
        b"payload-c",
        b"payload-d",
        b"payload-e",
    ]

    def _upload_once(content: bytes) -> int:
        with TestClient(enabled_app) as client:
            response = client.post(
                "/api/uploads",
                headers={"X-API-Key": raw_key},
                data={"filename": filename},
                files={"file": (filename, content, "text/plain")},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        statuses = list(pool.map(_upload_once, payloads))

    assert all(status == 201 for status in statuses)

    saved = (enabled_app.state.config.root / filename).read_bytes()
    assert saved in payloads

    with Session(enabled_app.state.db_engine) as db:
        events = db.exec(
            select(AuditLog)
            .where(AuditLog.action == "upload_success")
            .where(AuditLog.resource == filename)
        ).all()
        assert len(events) == len(payloads)
