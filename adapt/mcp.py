"""adapt.mcp — Model Context Protocol server exposing Adapt's resources as tools.

Mounted at `/mcp` on the same FastAPI app `adapt serve` already runs (see
`adapt.app.create_app`). Tools are thin wrappers over the same plugin methods
and permission checks the REST API and `/search` already use — no parallel
API surface, no duplicated authorization logic.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastapi import HTTPException, Request
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field
from sqlmodel import Session

from .auth.dependencies import check_permission, get_current_user
from .config import AdaptConfig
from .models import QueryParams
from .permissions import PermissionChecker
from .plugins.base import PluginContext
from .routes import ResourceRegistryEntry
from .routes_search import DATASET_TYPES, _run_search
from .storage import User

logger = logging.getLogger(__name__)

SortParam = Annotated[
    str | None,
    Field(description="Dataset column name to sort by, for example `category` or `price`."),
]
OrderParam = Annotated[
    Literal["asc", "desc"],
    Field(description="Sort direction for dataset reads. Use `sort` for the column name and `order` for `asc` or `desc`."),
]
FilterParam = Annotated[
    dict[str, Any] | None,
    Field(description="Optional dataset filter object, using the same shape as the REST API."),
]


async def _authenticated_user(ctx: Context) -> User:
    """Resolve the calling user from the request's `X-API-Key` header.

    MCP has no concept of an anonymous session the way an HTML page does, so
    every tool requires auth.
    """
    request = ctx.request_context.request
    user = get_current_user(request)
    if user is None:
        raise ToolError("Authentication required: send a valid X-API-Key header or Authorization Bearer token.")
    return user


def _authorized_entry(request: Request, user: User, namespace: str, action: str) -> ResourceRegistryEntry:
    """Look up a resource by namespace and enforce `action` permission on it."""
    entry = request.app.state.resource_registry.get(namespace)
    if entry is None:
        raise ToolError(f"Unknown resource: {namespace!r}")
    with Session(request.app.state.db_engine) as db:
        if not check_permission(user, db, action, namespace):
            raise ToolError(f"Permission denied: {action} on {namespace!r}")
    return entry


def build_mcp_server(config: AdaptConfig) -> FastMCP:
    """Construct the FastMCP server and register its tools.

    `streamable_http_path` is set to `/` because the outer app already mounts
    this server's ASGI app at `/mcp` (`app.mount("/mcp", mcp_app)`); leaving
    the SDK's own default of `/mcp` here would double up to `/mcp/mcp`.
    """
    mcp = FastMCP(
        name="adapt",
        instructions=(
            "Adapt exposes file-backed datasets, documents, and media as "
            "permission-filtered tools. Call list_resources first to see what "
            "you can read; search works across everything you're permitted to see."
        ),
        streamable_http_path="/",
    )

    @mcp.tool()
    async def list_resources(ctx: Context) -> dict:
        """List every resource namespace the caller may read, with its type."""
        request = ctx.request_context.request
        user = await _authenticated_user(ctx)
        registry: dict[str, ResourceRegistryEntry] = request.app.state.resource_registry

        if getattr(user, "is_superuser", False):
            readable = None
        else:
            with Session(request.app.state.db_engine) as db:
                readable = PermissionChecker(db).readable_resources(user)

        resources = [
            {"resource": namespace, "type": entry.resource.resource_type}
            for namespace, entry in registry.items()
            if readable is None or namespace in readable
        ]
        return {"resources": resources}

    @mcp.tool()
    async def get_schema(resource: str, ctx: Context) -> dict:
        """Return the schema for a dataset resource (columns and types)."""
        request = ctx.request_context.request
        user = await _authenticated_user(ctx)
        entry = _authorized_entry(request, user, resource, "read")
        return entry.plugin.schema(entry.descriptor)

    @mcp.tool()
    async def read_resource(
        resource: str,
        ctx: Context,
        limit: int | None = None,
        offset: int = 0,
        sort: SortParam = None,
        order: OrderParam = "asc",
        filter: FilterParam = None,
    ) -> Any:
        """Read a resource's content, permission-checked like the REST API.

        For dataset resources, `sort` is the column name and `order` must be
        `asc` or `desc`.
        """
        request = ctx.request_context.request
        user = await _authenticated_user(ctx)
        entry = _authorized_entry(request, user, resource, "read")
        request.state.user = user

        if entry.resource.resource_type in DATASET_TYPES:
            query_params = QueryParams(limit=limit, offset=offset, sort=sort, order=order, filter=filter)
            return entry.plugin.read(entry.descriptor, request, query_params)
        return entry.plugin.read(entry.descriptor, request)

    @mcp.tool()
    async def write_resource(
        resource: str,
        action: Literal["create", "update", "delete"],
        data: Any,
        ctx: Context,
    ) -> dict:
        """Create, update, or delete rows in a writable (dataset) resource."""
        request = ctx.request_context.request
        user = await _authenticated_user(ctx)
        entry = _authorized_entry(request, user, resource, "write")

        if request.app.state.config.readonly:
            raise ToolError("Server is in read-only mode")

        request.state.user = user
        context = PluginContext(
            engine=request.app.state.db_engine,
            root=request.app.state.config.root,
            readonly=request.app.state.config.readonly,
            lock_manager=request.app.state.lock_manager,
        )
        try:
            return entry.plugin.write(entry.descriptor, {"action": action, "data": data}, request, context)
        except NotImplementedError:
            raise ToolError(f"Resource type {entry.resource.resource_type!r} does not support write operations")
        except HTTPException as exc:
            raise ToolError(str(exc.detail))

    @mcp.tool()
    async def search(
        q: str,
        ctx: Context,
        limit: int = 20,
        offset: int = 0,
        resource_type: str | None = None,
    ) -> dict:
        """Full-text search across every resource the caller may read."""
        request = ctx.request_context.request
        user = await _authenticated_user(ctx)
        return _run_search(request, q, limit, offset, resource_type, user)

    return mcp
