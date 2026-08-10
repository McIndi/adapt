"""adapt.app — FastAPI application factory and middleware configuration."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, delete
from datetime import datetime, timezone

from .auth import router as auth_router
from .auth.dependencies import get_current_user
from .auth.session import get_session
from .admin import router as admin_router
from .admin.uploads import router as uploads_router
from .config import AdaptConfig
from .discovery import discover_resources
from .permissions import PermissionChecker
from .routes import build_resource_registry, generate_routes, resource_namespaces as _routes_resource_namespaces
from .routes_search import router as search_router, safe_snippet
from .storage import User, DBSession, init_database
from .locks import LockManager
from .mcp import build_mcp_server
from .utils import build_accessible_ui_links
from . import cache, search
from .security import (
    apply_security_headers,
    build_allowed_hosts,
    generate_csrf_token,
    set_csrf_cookie,
    validate_csrf,
)
from .security_urls import login_redirect_url

_START_TIME = time.time()

logger = logging.getLogger(__name__)

_DOCS_INTERNAL_PATHS = frozenset({"/docs", "/docs/", "/docs/oauth2-redirect", "/openapi.json"})
_PUBLIC_OPENAPI_PATHS = frozenset({"/", "/auth/login", "/health"})
_AUTHENTICATED_OPENAPI_PATHS = frozenset({"/auth/logout", "/auth/me", "/profile", "/api/apikeys", "/search"})


async def cleanup_expired_sessions(engine, interval_hours=24):
    """Background task to clean up expired sessions."""
    logger.debug("Starting background session cleanup task with interval %d hours", interval_hours)
    while True:
        await asyncio.sleep(interval_hours * 3600)
        
        with Session(engine) as db:
            now = datetime.now(tz=timezone.utc)
            stmt = delete(DBSession).where(DBSession.expires_at < now)
            result = db.exec(stmt)
            db.commit()
            
            if result.rowcount > 0:
                logger.info("Cleaned up %d expired sessions", result.rowcount)


def _normalize_path(path: str) -> str:
    """Normalize route paths so matching is consistent with and without trailing slashes."""
    normalized = path.rstrip("/")
    return normalized or "/"


def _resource_namespaces(resource) -> set[str]:
    """Return the supported permission namespaces for a discovered resource."""
    return set(_routes_resource_namespaces(resource))


def _all_resource_namespaces(resources) -> set[str]:
    """Collect all permission namespaces exposed by discovered resources."""
    namespaces: set[str] = set()
    for resource in resources:
        namespaces.update(_resource_namespaces(resource))
    return namespaces


def _visible_resource_namespaces(request: Request, user: User | None) -> set[str]:
    """Return the resource namespaces that should be visible to the current user."""
    resources = request.app.state.resources
    if not user:
        return set()

    if getattr(user, "is_superuser", False):
        return _all_resource_namespaces(resources)

    from .permissions import PermissionChecker

    visible: set[str] = set()
    with Session(request.app.state.db_engine) as db:
        checker = PermissionChecker(db)
        for resource in resources:
            for namespace in _resource_namespaces(resource):
                if checker.has_permission(user, namespace, "read"):
                    visible.add(namespace)
    return visible


def _can_upload_root(request: Request, user: User | None) -> bool:
    """Return whether the current user can upload to the document root."""
    if not user:
        return False

    if getattr(user, "is_superuser", False):
        return True

    config = request.app.state.config
    if config.readonly or not config.upload.get("enabled", False):
        return False

    with Session(request.app.state.db_engine) as db:
        checker = PermissionChecker(db)
        return checker.has_permission(user, "", "write")


def _extract_resource_namespace(path: str, all_namespaces: set[str]) -> str | None:
    """Extract the resource namespace from a route path if it maps to a discovered resource."""
    normalized_path = _normalize_path(path)
    stripped_path = normalized_path.lstrip("/")
    if stripped_path in all_namespaces:
        return stripped_path

    for prefix in ("/api/", "/schema/", "/ui/", "/media/"):
        if normalized_path.startswith(prefix):
            candidate = normalized_path[len(prefix):]
            if candidate in all_namespaces:
                return candidate
    return None


def _operation_is_visible(path: str, operation: dict, request: Request, user: User | None, all_namespaces: set[str], visible_namespaces: set[str]) -> bool:
    """Decide whether an OpenAPI operation should appear in the current request's schema."""
    path = _normalize_path(path)

    if path in _DOCS_INTERNAL_PATHS:
        return False

    if path.startswith("/admin") or "admin" in (operation.get("tags") or []):
        return bool(user and getattr(user, "is_superuser", False))

    if path in _PUBLIC_OPENAPI_PATHS:
        return True

    if path in _AUTHENTICATED_OPENAPI_PATHS:
        return user is not None

    if path == "/ui/media":
        media_namespaces = {
            ns
            for r in request.app.state.resources
            if r.resource_type == "media"
            for ns in _resource_namespaces(r)
        }
        return bool(media_namespaces & visible_namespaces)

    resource_namespace = _extract_resource_namespace(path, all_namespaces)
    if resource_namespace is not None:
        return resource_namespace in visible_namespaces

    if path.startswith("/auth/"):
        return user is not None

    return False


def _iter_schema_refs(node):
    """Yield component schema names referenced anywhere within a JSON-like node."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            yield ref.removeprefix("#/components/schemas/")
        for value in node.values():
            yield from _iter_schema_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_schema_refs(item)


def _prune_unreferenced_components(schema: dict) -> None:
    """Drop component schemas no longer reachable from any kept path.

    Filtering removes paths but leaves their request/response models behind in
    components.schemas — a non-superuser would otherwise receive the
    field-level shape of admin-only models like UserPublic or Permission.
    """
    components = schema.get("components") or {}
    schemas = components.get("schemas")
    if not schemas:
        return

    reachable: set[str] = set()
    pending = set(_iter_schema_refs(schema.get("paths", {})))
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.update(_iter_schema_refs(schemas.get(name, {})))

    pruned = {name: definition for name, definition in schemas.items() if name in reachable}
    if pruned:
        components["schemas"] = pruned
    else:
        components.pop("schemas", None)
    if not components:
        schema.pop("components", None)


def _build_openapi_schema(app: FastAPI, request: Request, user: User | None) -> dict:
    """Build a filtered OpenAPI schema for the current request context."""
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    all_namespaces = _all_resource_namespaces(request.app.state.resources)
    visible_namespaces = _visible_resource_namespaces(request, user)

    visible_paths: dict[str, dict] = {}
    for path, operations in schema.get("paths", {}).items():
        kept = {
            method: operation
            for method, operation in operations.items()
            if _operation_is_visible(path, operation, request, user, all_namespaces, visible_namespaces)
        }
        if kept:
            visible_paths[path] = kept

    schema["paths"] = visible_paths
    _prune_unreferenced_components(schema)
    return schema


def _visible_resource_paths(request: Request, user: User | None) -> list[str]:
    """Return resource paths visible to the current user for JSON discovery responses."""
    visible_namespaces = _visible_resource_namespaces(request, user)
    visible_resources: list[str] = []
    for resource in request.app.state.resources:
        if _resource_namespaces(resource) & visible_namespaces:
            visible_resources.append(resource.relative_path.as_posix())
    return visible_resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events.

    A mounted MCP sub-app's own `lifespan` is never invoked by the ASGI
    server: Starlette's `Mount` only forwards `http`/`websocket` scope types,
    never `lifespan`. So the MCP session manager's `run()` context must be
    entered here, alongside the rest of this app's own startup/shutdown.
    """
    # Startup: Start background cleanup task
    engine = app.state.db_engine
    cleanup_task = asyncio.create_task(cleanup_expired_sessions(engine))
    logger.debug("Application startup: background cleanup task started")

    mcp_server = getattr(app.state, "mcp_server", None)
    if mcp_server is not None:
        async with mcp_server.session_manager.run():
            yield
    else:
        yield

    # Shutdown: Could add cleanup logic here if needed
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.debug("Application shutdown: cleanup task cancelled")
    finally:
        engine.dispose()
        logger.debug("Application shutdown: database engine disposed")


def _init_infrastructure(config: AdaptConfig):
    """Initialize database, cache, lock manager, and resource discovery.

    Returns:
        Tuple of (engine, lock_manager, resources).
    """
    engine = init_database(config.db_path)
    cache.configure(str(config.db_path))
    search.configure(str(config.db_path))
    lock_manager = LockManager(engine)
    cleaned = lock_manager.release_stale_locks(max_age_seconds=300)
    if cleaned > 0:
        logging.warning("Cleaned %d stale locks on startup", cleaned)
    resources = discover_resources(config.root, config)
    logger.debug("Discovered %d resources", len(resources))
    if config.search_on_startup:
        # Incremental: unchanged files are skipped, so restarts stay cheap.
        search.reindex_all(resources, config)
    return engine, lock_manager, resources


def create_app(config: AdaptConfig) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: The application configuration.

    Returns:
        The configured FastAPI app instance.
    """
    logger.debug("Creating FastAPI app with config: %s", config)
    engine, lock_manager, resources = _init_infrastructure(config)

    app = FastAPI(title="Adapt", version=config.version, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.state.db_engine = engine
    app.state.use_tls = bool(config.tls_cert and config.tls_key)
    app.state.lock_manager = lock_manager
    app.state.resources = resources
    app.state.resource_registry = build_resource_registry(resources, config)

    allowed_hosts = build_allowed_hosts(config.host)
    if allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Set up Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    # Search snippets hold raw docroot text; this escapes them and restores only
    # the <mark> highlights. See routes_search.safe_snippet.
    templates.env.filters["safe_snippet"] = safe_snippet
    app.state.templates = templates

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Authentication middleware
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        """Middleware for CSRF validation and response security headers."""
        csrf_token = request.cookies.get("adapt_csrf")
        should_set_csrf_cookie = False
        if not csrf_token:
            csrf_token = generate_csrf_token()
            should_set_csrf_cookie = True

        request.state.csrf_token = csrf_token

        csrf_error = await validate_csrf(request)
        if csrf_error:
            apply_security_headers(csrf_error, use_tls=request.app.state.use_tls)
            if should_set_csrf_cookie:
                set_csrf_cookie(csrf_error, csrf_token, secure=request.app.state.config.secure_cookies)
            return csrf_error

        response = await call_next(request)
        apply_security_headers(response, use_tls=request.app.state.use_tls)
        if should_set_csrf_cookie:
            set_csrf_cookie(response, csrf_token, secure=request.app.state.config.secure_cookies)
        return response

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Middleware to handle user authentication via session cookies."""
        token = request.cookies.get("adapt_session")
        request.state.user = None
        if token:
            with Session(engine) as db:
                sess = get_session(db, token)  # Uses fixed function with expiration check
                if sess:
                    user = db.get(User, sess.user_id)
                    request.state.user = user
                    logger.debug("Authenticated user %s for request %s", user.username if user else None, request.url)
                else:
                    logger.debug("Invalid or expired session token for request %s", request.url)
        else:
            logger.debug("No session token in request %s", request.url)
        response = await call_next(request)
        return response

    # Mount authentication routes
    app.include_router(auth_router, prefix="", tags=["auth"])

    # Mount admin routes
    app.include_router(admin_router)

    # Mount upload routes
    app.include_router(uploads_router)

    # Mount search routes
    app.include_router(search_router)

    # Generate and mount routes
    generate_routes(app, app.state.resource_registry)

    # Mount the MCP server, exposing resources as agent-facing tools
    if config.mcp_enabled:
        mcp_server = build_mcp_server(config)
        mcp_app = mcp_server.streamable_http_app()
        # A mounted sub-app's `request.app` is itself, not the main app (see
        # lifespan() docstring for the related lifespan gotcha) — mirror the
        # slice of state every tool/helper needs onto it.
        mcp_app.state.db_engine = engine
        mcp_app.state.resources = resources
        mcp_app.state.config = config
        mcp_app.state.lock_manager = lock_manager
        mcp_app.state.resource_registry = app.state.resource_registry
        # The outer app's own middleware still runs for /mcp requests (it wraps
        # routing, including the Mount), and by the time it inspects
        # `request.app.state` post-routing, `scope["app"]` has already been
        # overwritten to `mcp_app` — so anything that middleware reads off
        # app.state must be mirrored here too, not just what the tools need.
        mcp_app.state.use_tls = app.state.use_tls
        app.state.mcp_server = mcp_server
        app.mount("/mcp", mcp_app)

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_schema(request: Request):
        """Return an OpenAPI document filtered to the current user's visible routes."""
        user = get_current_user(request)
        return JSONResponse(_build_openapi_schema(app, request, user))

    @app.get("/docs", include_in_schema=False)
    @app.get("/docs/", include_in_schema=False)
    def swagger_ui():
        """Render Swagger UI against the request-filtered OpenAPI schema."""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - API Docs",
            oauth2_redirect_url="/docs/oauth2-redirect",
        )

    @app.get("/docs/oauth2-redirect", include_in_schema=False)
    def swagger_ui_redirect():
        """Serve the Swagger UI OAuth redirect helper."""
        return get_swagger_ui_oauth2_redirect_html()
    
    @app.get("/health", tags=["system"])
    async def health(request: Request, user=Depends(get_current_user)):
        """
        Health check endpoint.
        - Unauthenticated: returns minimal info (status, version, timestamp)
        - Authenticated: adds uptime, cache size, and endpoint count
        """
        info = {
            "status": "ok",
            "version": getattr(config, "version", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        }
        if user:
            # Add extra info for authenticated users
            uptime = time.time() - _START_TIME
            # Try to get cache size if available
            cache_size = None
            try:
                conn = cache._get_conn()
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {cache.CACHE_TABLE}")
                cache_size = cursor.fetchone()[0]
                conn.close()
            except Exception:
                pass
            # Count endpoints
            endpoint_count = len(app.routes)
            info.update({
                "uptime_seconds": int(uptime),
                "cache_size": cache_size,
                "endpoint_count": endpoint_count
            })
        return JSONResponse(info)


    # Media gallery route
    @app.get("/ui/media")
    def media_gallery(request: Request):
        """Render the media gallery UI for authenticated users."""
        user = get_current_user(request)
        if not user:
            logger.debug("Unauthenticated access to media gallery, redirecting to login")
            return RedirectResponse(url=login_redirect_url("/ui/media"), status_code=302)

        all_media = [r for r in request.app.state.resources if r.resource_type == "media"]
        if getattr(user, "is_superuser", False):
            permitted_media = all_media
        else:
            with Session(engine) as db:
                checker = PermissionChecker(db)
                permitted_media = [
                    r for r in all_media
                    if checker.has_permission(user, r.relative_path.with_suffix("").as_posix(), "read")
                ]
        if not permitted_media and not getattr(user, "is_superuser", False):
            logger.warning("Permission denied for user %s: no accessible media resources", user.username)
            raise HTTPException(status_code=403, detail="No accessible media resources")

        media_items = []
        for r in permitted_media:
            media_items.append({
                "name": r.path.name,
                "relative_path": r.relative_path.as_posix(),
                "media_type": r.metadata.get("media_type", "unknown"),
                "file_size": r.metadata.get("file_size", 0),
                "duration": r.metadata.get("duration"),
                "bitrate": r.metadata.get("bitrate"),
                "title": r.metadata.get("title"),
                "artist": r.metadata.get("artist"),
                "album": r.metadata.get("album"),
                "genre": r.metadata.get("genre"),
                "thumbnail": r.metadata.get("thumbnail"),
            })
        accessible_resources = build_accessible_ui_links(request, user)
        context = {
            "media_items": media_items,
            "user": user,
            "ui_links": accessible_resources,
            "is_superuser": user and getattr(user, "is_superuser", False)
        }
        logger.debug("Rendering media gallery for user %s with %d items", user.username, len(media_items))
        return request.app.state.templates.TemplateResponse(request, "media_gallery.html", context)

    # Debug root route
    @app.get("/")
    def root(request: Request):
        """Handle root requests, rendering HTML landing page or JSON API response."""
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            # Render landing page
            user = get_current_user(request)
            accessible_resources = build_accessible_ui_links(request, user)
            can_upload_root = _can_upload_root(request, user)
            
            # Add media gallery link only if the user can access at least one media file
            if any(link["type"] == "media" for link in accessible_resources):
                accessible_resources.append({"name": "Media Gallery", "url": "/ui/media", "type": "media"})
            
            context = {
                "user": user,
                "ui_links": accessible_resources,
                "is_superuser": user and getattr(user, "is_superuser", False),
                "can_upload_root": can_upload_root,
            }
            logger.debug("Rendering HTML landing page for user %s", user.username if user else None)
            return request.app.state.templates.TemplateResponse(request, "landing.html", context)
        else:
            # JSON API response
            user = get_current_user(request)
            resources = _visible_resource_paths(request, user)
            logger.debug("Returning JSON API response with %d resources", len(resources))
            return {"resources": resources}

    # Exception handler for auth redirects
    @app.exception_handler(HTTPException)
    async def auth_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions, redirecting to login for 401 errors in HTML requests."""
        if exc.status_code == 401:
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                logger.debug("Redirecting unauthenticated request to login for %s", request.url)
                return RedirectResponse(url=login_redirect_url(request.url.path), status_code=302)
        
        logger.warning("HTTP exception %d: %s for request %s", exc.status_code, exc.detail, request.url)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return app
