from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, delete
from datetime import datetime, timezone

from .config import AdaptConfig
from .discovery import discover_resources
from .routes import generate_routes
from .storage import User, DBSession, init_database
from .locks import LockManager


async def cleanup_expired_sessions(engine, interval_hours=24):
    """Background task to clean up expired sessions."""
    while True:
        await asyncio.sleep(interval_hours * 3600)
        
        with Session(engine) as db:
            now = datetime.now(tz=timezone.utc)
            stmt = delete(DBSession).where(DBSession.expires_at < now)
            result = db.exec(stmt)
            db.commit()
            
            if result.rowcount > 0:
                print(f"Cleaned up {result.rowcount} expired sessions")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Startup: Start background cleanup task
    engine = app.state.db_engine
    cleanup_task = asyncio.create_task(cleanup_expired_sessions(engine))
    
    yield
    
    # Shutdown: Could add cleanup logic here if needed
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


def create_app(config: AdaptConfig) -> FastAPI:
    engine = init_database(config.db_path)
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

    # Debug root route
    @app.get("/")
    def root():
        return {"resources": [r.relative_path.as_posix() for r in resources]}

    # Exception handler for auth redirects
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse, RedirectResponse
    from fastapi import Request

    @app.exception_handler(HTTPException)
    async def auth_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == 401:
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                return RedirectResponse(url=f"/auth/login?next={request.url}", status_code=302)
        
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return app
