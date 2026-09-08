from fastapi import Request, Response, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from pydantic import BaseModel
import logging
import secrets

from ..storage import User, DBSession, APIKey, get_db_session
from ..audit import log_action
from ..api_keys import create_api_key_record, revoke_api_key_record
from ..utils import build_accessible_ui_links
from .password import update_password, verify_password
from ..commands.passwords import is_weak_password
from .session import create_session, SESSION_COOKIE
from .dependencies import require_auth
from .oidc import (
    OIDC_COOKIE_MAX_AGE,
    OIDC_NEXT_COOKIE,
    OIDC_STATE_COOKIE,
    OIDC_VERIFIER_COOKIE,
    authorization_redirect_url,
    end_session_url,
    exchange_code,
    generate_pkce_pair,
    sync_oidc_user,
    validate_access_token,
)
from . import router
from ..security_urls import is_safe_next_path, normalize_next_path

logger = logging.getLogger(__name__)

class APIKeyCreateRequest(BaseModel):
    description: str | None = None
    expires_in_days: int | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

def _set_oidc_cookie(response: Response, key: str, value: str, secure: bool) -> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=OIDC_COOKIE_MAX_AGE,
        path="/",
    )


def _clear_oidc_cookies(response: Response) -> None:
    for key in (OIDC_STATE_COOKIE, OIDC_VERIFIER_COOKIE, OIDC_NEXT_COOKIE):
        response.delete_cookie(key=key, path="/")


@router.get("/auth/login")
def login_page(request: Request):
    """Render the login page."""
    config = request.app.state.config
    logger.debug("Rendering login page")
    return request.app.state.templates.TemplateResponse(request, "login.html", {
        "oidc_enabled": config.oidc_enabled(),
        "local_login": config.local_login_enabled(),
    })

@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), request: Request = None, response: Response = None):
    """Handle user login."""
    # form.username, form.password
    db_engine = request.app.state.db_engine
    config = request.app.state.config
    if not config.local_login_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local password login is disabled")
    with Session(db_engine) as db:
        stmt = select(User).where(User.username == form.username)
        user = db.exec(stmt).first()
        if not user or not user.is_active or not verify_password(form.password, user.password_hash):
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

@router.get("/auth/oidc/login")
def oidc_login(request: Request):
    """Start the OIDC authorization-code + PKCE flow."""
    config = request.app.state.config
    if not config.oidc_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC is not configured")
    if not config.oidc_public_url():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OIDC public_url is not configured")
    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    try:
        redirect_to = authorization_redirect_url(config, state, challenge)
    except Exception:
        logger.exception("Failed to start OIDC login")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OIDC discovery failed")
    response = RedirectResponse(url=redirect_to, status_code=302)
    secure = config.secure_cookies
    _set_oidc_cookie(response, OIDC_STATE_COOKIE, state, secure)
    _set_oidc_cookie(response, OIDC_VERIFIER_COOKIE, verifier, secure)
    next_path = request.query_params.get("next")
    if is_safe_next_path(next_path):
        _set_oidc_cookie(response, OIDC_NEXT_COOKIE, normalize_next_path(next_path), secure)
    return response


@router.get("/auth/oidc/callback")
def oidc_callback(request: Request):
    """Complete OIDC login: exchange code, JIT sync, set session cookie."""
    config = request.app.state.config
    if not config.oidc_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC is not configured")
    error = request.query_params.get("error")
    if error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error)
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    expected_state = request.cookies.get(OIDC_STATE_COOKIE)
    verifier = request.cookies.get(OIDC_VERIFIER_COOKIE)
    if not code or not state or not expected_state or not verifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OIDC callback parameters")
    if not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OIDC state")
    try:
        tokens = exchange_code(config, code, verifier)
    except Exception:
        logger.exception("OIDC token exchange failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC token exchange failed")
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC token response missing access_token")
    claims = validate_access_token(config, access_token)
    if claims is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OIDC access token")
    with Session(request.app.state.db_engine) as db:
        user = sync_oidc_user(db, config, claims)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        session_token = create_session(db, user.id, id_token=id_token if isinstance(id_token, str) else None)
        log_action(request, "login", "auth", "User logged in via OIDC", user.id)
        logger.info("User %s logged in via OIDC", user.username)
    next_path = normalize_next_path(request.cookies.get(OIDC_NEXT_COOKIE))
    response = RedirectResponse(url=next_path, status_code=302)
    response.set_cookie(
        key="adapt_session",
        value=session_token,
        httponly=True,
        secure=config.secure_cookies,
        samesite="lax",
        max_age=int((7 * 24 * 60 * 60)),
    )
    _clear_oidc_cookies(response)
    return response

@router.post("/auth/logout")
def logout(request: Request, response: Response):
    """Handle user logout. Redirect to Keycloak end_session when an id_token is stored."""
    token = request.cookies.get(SESSION_COOKIE)
    id_token = None
    if token:
        db_engine = request.app.state.db_engine
        with Session(db_engine) as db:
            stmt = select(DBSession).where(DBSession.token == token)
            sess = db.exec(stmt).first()
            if sess:
                id_token = sess.id_token
                log_action(request, "logout", "auth", "User logged out", sess.user_id)
                logger.info("User %d logged out", sess.user_id)
                db.delete(sess)
                db.commit()
        response.delete_cookie(key=SESSION_COOKIE)
    else:
        logger.debug("Logout attempted without session cookie")
    redirect_url = "/auth/login"
    config = request.app.state.config
    if id_token and config.oidc_enabled():
        kc_logout = end_session_url(config, id_token)
        if kc_logout:
            redirect_url = kc_logout
    return RedirectResponse(url=redirect_url, status_code=302)

@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_auth)):
    """Render the user profile page."""
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
    return {"id": user.id, "username": user.username, "is_superuser": getattr(user, "is_superuser", False)}


@router.put("/auth/password")
def change_password(
    password_data: PasswordChangeRequest,
    request: Request,
    response: Response,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db_session),
):
    """Change the current user's password and revoke their browser sessions."""
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if verify_password(password_data.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="New password must be different")
    if is_weak_password(password_data.new_password, username=user.username):
        raise HTTPException(status_code=400, detail="New password is too weak")

    update_password(db, user, password_data.new_password)
    log_action(request, "change_password", "auth", "User changed password", user.id)
    response.delete_cookie(key=SESSION_COOKIE)
    return {"message": "Password changed. Sign in again."}


@router.post("/api/apikeys", status_code=201)
def create_api_key(
    request: APIKeyCreateRequest,
    req: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db_session)
):
    """Create a new API key for the authenticated user."""
    if req.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")

    logger.debug("User %s creating API key", user.username)

    try:
        raw_key, api_key = create_api_key_record(db, user.id, request.description, request.expires_in_days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action(req, "create_api_key", "apikey", f"Created API key for user {user.username}", user.id)
    logger.info("User %s created API key %d", user.username, api_key.id)

    return {
        "id": api_key.id,
        "key": raw_key,  # Only returned once
        "description": api_key.description,
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "created_at": api_key.created_at.isoformat(),
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
    if req.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")

    logger.debug("User %s revoking API key %d", user.username, key_id)

    api_key = revoke_api_key_record(db, key_id, owner_id=user.id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    log_action(req, "revoke_api_key", "apikey", f"Revoked API key {key_id} for user {user.username}", user.id)
    logger.info("User %s revoked API key %d", user.username, key_id)
