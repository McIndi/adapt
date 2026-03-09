from fastapi import Request, Response, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import logging

from ..storage import User, DBSession, APIKey, get_db_session
from ..config import AdaptConfig
from ..audit import log_action
from ..api_keys import generate_api_key
from .password import verify_password
from .session import create_session
from .dependencies import require_auth
from . import router

logger = logging.getLogger(__name__)

class APIKeyCreateRequest(BaseModel):
    description: str | None = None
    expires_in_days: int | None = None

@router.get("/auth/login")
def login_page(request: Request):
    """Render the login page."""
    logger.debug("Rendering login page")
    return request.app.state.templates.TemplateResponse(request, "login.html")

@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), request: Request = None, response: Response = None):
    """Handle user login."""
    # form.username, form.password
    db_engine = request.app.state.db_engine
    config = request.app.state.config
    with Session(db_engine) as db:
        stmt = select(User).where(User.username == form.username)
        user = db.exec(stmt).first()
        if not user or not verify_password(form.password, user.password_hash):
            logger.warning("Failed login attempt for username %s", form.username)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_session(db, user.id)
        
        log_action(request, "login", "auth", "User logged in", user.id)
        logger.info("User %s logged in", user.username)
        
        # Set cookie (HttpOnly, Secure based on config, SameSite=lax)
        response.set_cookie(
            key="adapt_session",
            value=token,
            httponly=True,
            secure=config.secure_cookies,
            samesite='lax',
            max_age=int((7 * 24 * 60 * 60))  # 7 days
        )
        return {"message": "Logged in"}

@router.post("/auth/logout")
def logout(request: Request, response: Response):
    """Handle user logout."""
    from .session import SESSION_COOKIE
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db_engine = request.app.state.db_engine
        with Session(db_engine) as db:
            stmt = select(DBSession).where(DBSession.token == token)
            sess = db.exec(stmt).first()
            if sess:
                log_action(request, "logout", "auth", "User logged out", sess.user_id)
                logger.info("User %d logged out", sess.user_id)
                
                db.delete(sess)
                db.commit()
        response.delete_cookie(key=SESSION_COOKIE)
    else:
        logger.debug("Logout attempted without session cookie")
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_auth)):
    """Render the user profile page."""
    from ..utils import build_accessible_ui_links
    ui_links = build_accessible_ui_links(request, user)
    logger.debug("Rendering profile page for user %s", user.username)
    return request.app.state.templates.TemplateResponse(request, "profile.html", {
        "user": user, 
        "is_superuser": getattr(user, "is_superuser", False),
        "ui_links": ui_links
    })

@router.get("/auth/me")
def me(user: User = Depends(require_auth)):
    """Get current user information."""
    logger.debug("User %s requested their info", user.username)
    return {"username": user.username, "is_superuser": getattr(user, "is_superuser", False)}


@router.post("/api/apikeys", status_code=201)
def create_api_key(
    request: APIKeyCreateRequest,
    req: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db_session)
):
    """Create a new API key for the authenticated user."""
    # Check if server is in read-only mode
    if req.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    logger.debug("User %s creating API key", user.username)
    
    # Validate expiration
    expires_at = None
    if request.expires_in_days is not None:
        if request.expires_in_days > 365:
            raise HTTPException(status_code=400, detail="Expiration cannot exceed 1 year (365 days)")
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=request.expires_in_days)
    
    # Generate key
    raw_key, key_hash = generate_api_key()
    
    # Create API key record
    api_key = APIKey(
        key_hash=key_hash,
        user_id=user.id,
        description=request.description,
        expires_at=expires_at,
        created_at=datetime.now(tz=timezone.utc),
        is_active=True
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    # Log audit
    log_action(req, "create_api_key", "apikey", f"Created API key for user {user.username}", user.id)
    
    logger.info("User %s created API key %d", user.username, api_key.id)
    return {
        "id": api_key.id,
        "key": raw_key,  # Only returned once
        "description": api_key.description,
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "created_at": api_key.created_at.isoformat()
    }


@router.get("/api/apikeys")
def list_api_keys(
    req: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db_session)
):
    """List API keys for the authenticated user."""
    logger.debug("User %s listing API keys", user.username)
    
    stmt = select(APIKey).where(APIKey.user_id == user.id)
    api_keys = db.exec(stmt).all()
    
    return [
        {
            "id": key.id,
            "description": key.description,
            "created_at": key.created_at.isoformat(),
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            "is_active": key.is_active
        }
        for key in api_keys
    ]


@router.delete("/api/apikeys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: int,
    req: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db_session)
):
    """Revoke an API key owned by the authenticated user."""
    # Check if server is in read-only mode
    if req.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    logger.debug("User %s revoking API key %d", user.username, key_id)
    
    api_key = db.get(APIKey, key_id)
    if not api_key or api_key.user_id != user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = False
    db.add(api_key)
    db.commit()
    
    # Log audit
    log_action(req, "revoke_api_key", "apikey", f"Revoked API key {key_id} for user {user.username}", user.id)
    
    logger.info("User %s revoked API key %d", user.username, key_id)