from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import datetime, timezone
import time
from .auth.dependencies import get_current_user
_START_TIME = time.time()
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, delete
from datetime import datetime, timezone

from .config import AdaptConfig
from .discovery import discover_resources
from .routes import generate_routes
from .storage import User, DBSession, init_database
from .locks import LockManager
from .utils import build_accessible_ui_links
from . import cache

logger = logging.getLogger(__name__)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Startup: Start background cleanup task
    engine = app.state.db_engine
    cleanup_task = asyncio.create_task(cleanup_expired_sessions(engine))
    logger.debug("Application startup: background cleanup task started")
    
    yield
    
    # Shutdown: Could add cleanup logic here if needed
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.debug("Application shutdown: cleanup task cancelled")


def create_app(config: AdaptConfig) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: The application configuration.

    Returns:
        The configured FastAPI app instance.
    """
    logger.debug("Creating FastAPI app with config: %s", config)
    engine = init_database(config.db_path)
    cache.configure(str(config.db_path))
    app = FastAPI(title="Adapt", version=config.version, lifespan=lifespan)
    app.state.config = config
    app.state.db_engine = engine
    
    # Initialize lock manager
    lock_manager = LockManager(engine)
    # Clean up stale locks from previous crash
    cleaned = lock_manager.release_stale_locks(max_age_seconds=300)  # 5 minutes
    if cleaned > 0:
        logging.warning(f"Cleaned {cleaned} stale locks on startup")
    app.state.lock_manager = lock_manager
    
    resources = discover_resources(config.root, config)
    app.state.resources = resources
    logger.debug("Discovered %d resources", len(resources))

    # Set up Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    app.state.templates = templates

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Authentication middleware
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Middleware to handle user authentication via session cookies."""
        from .auth.session import get_session
        from sqlmodel import Session
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
    from .auth import router as auth_router
    app.include_router(auth_router, prefix="", tags=["auth"])

    # Mount admin routes
    from .admin import router as admin_router
    app.include_router(admin_router)

    # Generate and mount routes
    generate_routes(app, resources, config)
    
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
        from .auth.dependencies import get_current_user
        user = get_current_user(request)
        if not user:
            # Redirect to login if not authenticated
            logger.debug("Unauthenticated access to media gallery, redirecting to login")
            return RedirectResponse(url=f"/auth/login?next=/ui/media", status_code=302)
        
        media_resources = [r for r in request.app.state.resources if r.resource_type == "media"]
        media_items = []
        for r in media_resources:
            # Check permission, but for simplicity, assume read permission
            # In full impl, check permission
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
        from .auth.dependencies import get_current_user
        from .utils import build_accessible_ui_links
        
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            # Render landing page
            user = get_current_user(request)
            accessible_resources = build_accessible_ui_links(request, user)
            
            # Add media gallery if there are media files
            if any(r.resource_type == "media" for r in request.app.state.resources):
                accessible_resources.append({"name": "Media Gallery", "url": "/ui/media", "type": "media"})
            
            context = {
                "user": user,
                "ui_links": accessible_resources,
                "is_superuser": user and getattr(user, "is_superuser", False)
            }
            logger.debug("Rendering HTML landing page for user %s", user.username if user else None)
            return request.app.state.templates.TemplateResponse(request, "landing.html", context)
        else:
            # JSON API response
            resources = [r.relative_path.as_posix() for r in request.app.state.resources]
            logger.debug("Returning JSON API response with %d resources", len(resources))
            return {"resources": resources}

    # Exception handler for auth redirects
    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def auth_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions, redirecting to login for 401 errors in HTML requests."""
        if exc.status_code == 401:
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                logger.debug("Redirecting unauthenticated request to login for %s", request.url)
                return RedirectResponse(url=f"/auth/login?next={request.url}", status_code=302)
        
        logger.warning("HTTP exception %d: %s for request %s", exc.status_code, exc.detail, request.url)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return app
