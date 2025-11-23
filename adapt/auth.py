from __future__ import annotations

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, status, Response, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from .storage import User, DBSession, init_database
from .config import AdaptConfig

# Password utilities (same as in cli)
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, digest = hashed.split("$")
    except ValueError:
        return False
    new_digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return secrets.compare_digest(new_digest, digest)

# Session handling
SESSION_COOKIE = "adapt_session"
SESSION_TTL = timedelta(days=7)

def create_session(db: Session, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(tz=timezone.utc)
    session_obj = DBSession(
        user_id=user_id,
        token=token,
        created_at=now,
        expires_at=now + SESSION_TTL,
        last_active=now,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return token

def get_session(db: Session, token: str) -> DBSession | None:
    now = datetime.now(tz=timezone.utc)
    stmt = (
        select(DBSession)
        .where(DBSession.token == token)
        .where(DBSession.expires_at > now)  # Enforce expiration
    )
    session = db.exec(stmt).first()
    
    if session:
        # Update last_active for sliding expiration
        session.last_active = now
        db.add(session)
        db.commit()
    else:
        # Constant-time dummy operation to mitigate timing attacks
        hmac.new(b"dummy_key", token.encode(), "sha256").digest()
    
    return session

def get_current_user(request: Request) -> User | None:
    # 1. Try Session Cookie
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with Session(request.app.state.db_engine) as db:
            session = get_session(db, token)
            if session:
                user = db.get(User, session.user_id)
                if user:
                    return user

    # 2. Try API Key
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        from .api_keys import verify_api_key
        with Session(request.app.state.db_engine) as db:
            user = verify_api_key(db, api_key_header)
            if user:
                return user

    return None

def require_auth(request: Request) -> User:
    user = get_current_user(request)
    if not user:
        # Check if it's an API request (JSON) or Browser request
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
             # Redirect to login for browser
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        else:
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

def require_superuser(user: User = Depends(require_auth)) -> User:
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required")
    return user

def check_permission(user: User, db: Session, action: str, resource: str) -> bool:
    """Check if a user has a specific permission via their groups."""
    if getattr(user, "is_superuser", False):
        return True
        
    # Query: User -> UserGroup -> Group -> GroupPermission -> Permission
    # We want to see if any of the user's groups have the required permission
    from .storage import UserGroup, GroupPermission, Permission
    
    stmt = (
        select(Permission)
        .join(GroupPermission, GroupPermission.permission_id == Permission.id)
        .join(UserGroup, UserGroup.group_id == GroupPermission.group_id)
        .where(UserGroup.user_id == user.id)
        .where(Permission.action == action)
        .where(Permission.resource == resource)
    )
    result = db.exec(stmt).first()
    return result is not None

def permission_dependency(action_param: str, resource: str):
    async def check(request: Request, user: User = Depends(require_auth)):
        # Determine action
        action = action_param
        if action == "auto":
            if request.method == "GET":
                action = "read"
            elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
                action = "write"
            else:
                action = "read"

        # Use proper session management with context manager
        with Session(request.app.state.db_engine) as db:
            try:
                if not check_permission(user, db, action, resource):
                     raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, 
                        detail=f"Permission denied: {action} on {resource}"
                    )
                db.commit()  # Commit if successful
                return user
            except Exception:
                db.rollback()  # Rollback on error
                raise
    return check

# FastAPI router for auth endpoints
from fastapi import APIRouter

router = APIRouter()

@router.get("/auth/login")
def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(request, "login.html")

@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), request: Request = None, response: Response = None):
    # form.username, form.password
    db_engine = request.app.state.db_engine
    config = request.app.state.config
    with Session(db_engine) as db:
        stmt = select(User).where(User.username == form.username)
        user = db.exec(stmt).first()
        if not user or not verify_password(form.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_session(db, user.id)
        
        from .audit import log_action
        log_action(request, "login", "auth", "User logged in", user.id)
        
        # Set cookie (HttpOnly, Secure based on config, SameSite=lax)
        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            httponly=True,
            secure=config.secure_cookies,
            samesite='lax',
            max_age=int(SESSION_TTL.total_seconds())
        )
        return {"message": "Logged in"}

@router.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db_engine = request.app.state.db_engine
        with Session(db_engine) as db:
            stmt = select(DBSession).where(DBSession.token == token)
            sess = db.exec(stmt).first()
            if sess:
                from .audit import log_action
                log_action(request, "logout", "auth", "User logged out", sess.user_id)
                
                db.delete(sess)
                db.commit()
        response.delete_cookie(key=SESSION_COOKIE)
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/auth/me")
def me(user: User = Depends(require_auth)):
    return {"username": user.username, "is_superuser": getattr(user, "is_superuser", False)}
