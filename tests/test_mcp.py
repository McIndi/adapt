"""Tests for the MCP server mounted at /mcp (adapt.mcp).

MCP's streamable-HTTP transport needs a real ASGI event loop serving SSE;
`fastapi.testclient.TestClient` doesn't speak the protocol. These tests spin
up the app with `uvicorn.Server` on an ephemeral port in a background thread
and drive it with `mcp.client.streamable_http.streamable_http_client` +
`mcp.ClientSession`.
"""
from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import httpx2
import pytest
import uvicorn
from sqlmodel import Session, select

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from adapt.api_keys import create_api_key_record
from adapt.app import create_app
from adapt.auth.password import hash_password
from adapt.config import AdaptConfig
from adapt.storage import AuditLog, Action, Group, GroupPermission, Permission, User, UserGroup


class _TestServer(uvicorn.Server):
    """uvicorn.Server that doesn't try to install signal handlers off the main thread."""

    def install_signal_handlers(self) -> None:
        pass


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(name="docroot")
def docroot_fixture(tmp_path):
    root = tmp_path / "docroot"
    root.mkdir()
    (root / "a.csv").write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")
    (root / "b.csv").write_text("name,age\nCarol,40\n", encoding="utf-8")
    (root / "notes.md").write_text("# Notes\n\nSome parental leave content.\n", encoding="utf-8")
    return root


@pytest.fixture(name="live_server")
def live_server_fixture(docroot):
    """Run a real adapt app over HTTP, yielding (base_url, app)."""
    config = AdaptConfig(root=docroot)
    app = create_app(config)

    port = _free_port()
    server = _TestServer(config=uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started, "uvicorn server failed to start"

    yield f"http://127.0.0.1:{port}", app

    server.should_exit = True
    thread.join(timeout=5)


def _make_user_with_key(app, username, *, superuser=False, reads=(), writes=()):
    """Create a user with an API key and the given read/write namespace permissions."""
    with Session(app.state.db_engine) as db:
        user = User(username=username, password_hash=hash_password("pw"), is_superuser=superuser)
        db.add(user)
        db.commit()
        db.refresh(user)

        for namespace, action in [(ns, Action.read) for ns in reads] + [(ns, Action.write) for ns in writes]:
            perm = Permission(resource=namespace, action=action)
            db.add(perm)
            db.commit()
            db.refresh(perm)
            group = Group(name=f"{namespace}_{action.value}_{username}")
            db.add(group)
            db.commit()
            db.refresh(group)
            db.add(GroupPermission(group_id=group.id, permission_id=perm.id))
            db.add(UserGroup(user_id=user.id, group_id=group.id))
            db.commit()

        raw_key, _ = create_api_key_record(db, user.id, "test key", None)
        db.refresh(user)
        return user, raw_key


async def _call(base_url, headers, tool, arguments=None):
    """Call a single MCP tool over streamable-HTTP and return the CallToolResult."""
    timeout = httpx2.Timeout(30, read=300)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as http_client:
        async with streamable_http_client(f"{base_url}/mcp", http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, arguments or {})


async def _list_tools(base_url, headers):
    timeout = httpx2.Timeout(30, read=300)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as http_client:
        async with streamable_http_client(f"{base_url}/mcp", http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.list_tools()


def _result_json(result):
    """Decode a tool result's content into JSON.

    MCPServer emits a list-returning tool as one TextContent block per item, so
    a single block decodes to one value but multiple blocks must be
    recombined into a list.
    """
    assert not result.is_error, result.content
    if len(result.content) == 1:
        return json.loads(result.content[0].text)
    return [json.loads(block.text) for block in result.content]


# ---------------------------------------------------------------------------
# 1. Tool discovery
# ---------------------------------------------------------------------------

def test_list_tools_returns_the_five_tools(live_server):
    base_url, _ = live_server
    tools = asyncio.run(_list_tools(base_url, headers={}))
    names = {t.name for t in tools.tools}
    assert names == {"list_resources", "get_schema", "read_resource", "write_resource", "search"}
    for tool in tools.tools:
        assert tool.description
        assert tool.input_schema


def test_read_resource_tool_schema_guides_sort_and_order_usage(live_server):
    base_url, _ = live_server
    tools = asyncio.run(_list_tools(base_url, headers={}))
    read_resource = next(tool for tool in tools.tools if tool.name == "read_resource")
    props = read_resource.input_schema["properties"]

    assert props["order"]["enum"] == ["asc", "desc"]
    assert "column name" in props["sort"]["description"].lower()
    assert "asc" in props["order"]["description"].lower()
    assert "desc" in props["order"]["description"].lower()


# ---------------------------------------------------------------------------
# 2. Auth is required for every tool
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,args", [
    ("list_resources", {}),
    ("get_schema", {"resource": "a"}),
    ("read_resource", {"resource": "a"}),
    ("write_resource", {"resource": "a", "action": "create", "data": []}),
    ("search", {"q": "x"}),
])
def test_tools_require_authentication(live_server, tool, args):
    base_url, _ = live_server
    result = asyncio.run(_call(base_url, headers={}, tool=tool, arguments=args))
    assert result.is_error
    assert "authentication" in result.content[0].text.lower()


# ---------------------------------------------------------------------------
# 3. Permission boundaries: list_resources / search / read_resource
# ---------------------------------------------------------------------------

def test_list_resources_respects_permissions(live_server):
    base_url, app = live_server
    _, raw_key = _make_user_with_key(app, "narrow", reads=["a"])

    result = asyncio.run(_call(base_url, headers={"X-API-Key": raw_key}, tool="list_resources"))
    payload = _result_json(result)
    namespaces = {r["resource"] for r in payload["resources"]}
    assert "a" in namespaces or "a.csv" in namespaces
    assert "b" not in namespaces and "b.csv" not in namespaces


def test_read_resource_respects_permissions(live_server):
    base_url, app = live_server
    _, raw_key = _make_user_with_key(app, "narrow2", reads=["a"])
    headers = {"X-API-Key": raw_key}

    ok = asyncio.run(_call(base_url, headers=headers, tool="read_resource", arguments={"resource": "a"}))
    assert not ok.is_error

    denied = asyncio.run(_call(base_url, headers=headers, tool="read_resource", arguments={"resource": "b"}))
    assert denied.is_error
    assert "permission denied" in denied.content[0].text.lower()


def test_search_respects_permissions(live_server):
    base_url, app = live_server
    _, raw_key = _make_user_with_key(app, "narrow3", reads=["a"])
    headers = {"X-API-Key": raw_key}

    result = asyncio.run(_call(base_url, headers=headers, tool="search", arguments={"q": "Alice"}))
    payload = _result_json(result)
    assert {r["resource"] for r in payload["results"]} <= {"a"}

    result = asyncio.run(_call(base_url, headers=headers, tool="search", arguments={"q": "Carol"}))
    payload = _result_json(result)
    assert payload["results"] == []


# ---------------------------------------------------------------------------
# 4. write_resource
# ---------------------------------------------------------------------------

def test_write_resource_succeeds_and_is_reflected_in_read(live_server):
    base_url, app = live_server
    user, raw_key = _make_user_with_key(app, "writer", reads=["a"], writes=["a"])
    headers = {"X-API-Key": raw_key}

    write_result = asyncio.run(_call(
        base_url, headers=headers, tool="write_resource",
        arguments={"resource": "a", "action": "create", "data": [{"name": "Dana", "age": "22"}]},
    ))
    assert not write_result.is_error, write_result.content

    read_result = asyncio.run(_call(base_url, headers=headers, tool="read_resource", arguments={"resource": "a"}))
    rows = _result_json(read_result)
    assert any(row.get("name") == "Dana" for row in rows)

    with Session(app.state.db_engine) as db:
        audit_entry = db.exec(
            select(AuditLog).where(AuditLog.action == "create_dataset_rows")
        ).one()

    assert audit_entry.user_id == user.id
    assert audit_entry.resource == "a.csv"
    assert audit_entry.details == "Created 1 dataset row"


def test_write_resource_fails_for_unpermitted_user(live_server):
    base_url, app = live_server
    _, raw_key = _make_user_with_key(app, "reader_only", reads=["a"])
    headers = {"X-API-Key": raw_key}

    result = asyncio.run(_call(
        base_url, headers=headers, tool="write_resource",
        arguments={"resource": "a", "action": "create", "data": [{"name": "X", "age": "1"}]},
    ))
    assert result.is_error
    assert "permission denied" in result.content[0].text.lower()


def test_write_resource_fails_when_readonly(live_server_readonly):
    base_url, app = live_server_readonly
    _, raw_key = _make_user_with_key(app, "writer_ro", reads=["a"], writes=["a"])
    headers = {"X-API-Key": raw_key}

    result = asyncio.run(_call(
        base_url, headers=headers, tool="write_resource",
        arguments={"resource": "a", "action": "create", "data": [{"name": "X", "age": "1"}]},
    ))
    assert result.is_error
    assert "read-only" in result.content[0].text.lower()


def test_write_resource_fails_for_non_dataset_resource(live_server):
    base_url, app = live_server
    _, raw_key = _make_user_with_key(app, "writer_md", reads=["notes"], writes=["notes"])
    headers = {"X-API-Key": raw_key}

    result = asyncio.run(_call(
        base_url, headers=headers, tool="write_resource",
        arguments={"resource": "notes", "action": "create", "data": {}},
    ))
    assert result.is_error
    assert "does not support write" in result.content[0].text.lower()


# ---------------------------------------------------------------------------
# 5. get_schema matches GET /schema/<ns>
# ---------------------------------------------------------------------------

def test_get_schema_matches_rest_endpoint(live_server):
    from fastapi.testclient import TestClient

    base_url, app = live_server
    user, raw_key = _make_user_with_key(app, "schema_reader", reads=["a"])

    result = asyncio.run(_call(base_url, headers={"X-API-Key": raw_key}, tool="get_schema", arguments={"resource": "a"}))
    mcp_schema = _result_json(result)

    rest_client = TestClient(app)
    rest_response = rest_client.get("/schema/a", headers={"X-API-Key": raw_key})
    assert rest_response.status_code == 200
    assert mcp_schema == rest_response.json()


# ---------------------------------------------------------------------------
# 6. Version-shape canary
# ---------------------------------------------------------------------------

def test_mcp_server_shape_is_reachable(docroot):
    from adapt.mcp import build_mcp_asgi_app, build_mcp_server

    config = AdaptConfig(root=docroot)
    mcp_server = build_mcp_server(config)
    mcp_app = build_mcp_asgi_app(mcp_server, config)
    assert mcp_server.session_manager is not None
    assert any(getattr(route, "path", None) == "/" for route in mcp_app.routes)


def test_mcp_mounted_on_main_app(live_server):
    base_url, app = live_server
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


# ---------------------------------------------------------------------------
# 7. mcp_enabled=False
# ---------------------------------------------------------------------------

def test_mcp_disabled_mounts_no_route(tmp_path):
    from fastapi.testclient import TestClient

    root = tmp_path / "docroot"
    root.mkdir()
    (root / "a.csv").write_text("name\nAlice\n", encoding="utf-8")

    config = AdaptConfig(root=root)
    config.mcp_enabled = False
    app = create_app(config)

    assert not any(getattr(route, "path", None) == "/mcp" for route in app.routes)
    assert not hasattr(app.state, "mcp_server")

    client = TestClient(app)
    assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# 8. MCP Host header (DNS rebinding)
# ---------------------------------------------------------------------------

def test_mcp_dns_rebinding_hosts_for_localhost():
    from adapt.security import mcp_dns_rebinding_hosts

    hosts = mcp_dns_rebinding_hosts("127.0.0.1")
    assert hosts is not None
    assert "127.0.0.1:*" in hosts
    assert "testserver" in hosts


def test_mcp_dns_rebinding_hosts_disabled_on_bind_all():
    from adapt.security import mcp_dns_rebinding_hosts

    assert mcp_dns_rebinding_hosts("0.0.0.0") is None


def test_mcp_dns_rebinding_hosts_adds_public_url():
    from adapt.security import mcp_dns_rebinding_hosts

    hosts = mcp_dns_rebinding_hosts("0.0.0.0", "https://adapt.example.com")
    assert hosts is not None
    assert "adapt.example.com" in hosts
    assert "adapt.example.com:*" in hosts


@pytest.fixture(name="live_server_readonly")
def live_server_readonly_fixture(docroot):
    """Same as live_server but with the server in read-only mode."""
    config = AdaptConfig(root=docroot)
    config.readonly = True
    app = create_app(config)

    port = _free_port()
    server = _TestServer(config=uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started, "uvicorn server failed to start"

    yield f"http://127.0.0.1:{port}", app

    server.should_exit = True
    thread.join(timeout=5)
