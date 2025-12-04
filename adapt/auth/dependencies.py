from fastapi import Request, HTTPException, status, Depends
from sqlmodel import Session, select
import logging

from ..storage import User, UserGroup, GroupPermission, Permission

logger = logging.getLogger(__name__)

def get_current_user(request: Request) -> User | None:
    """Get the current authenticated user from session or API key."""
    # 1. Try Session Cookie
    from .session import get_session
    token = request.cookies.get("adapt_session")
    if token:
        with Session(request.app.state.db_engine) as db:
            session = get_session(db, token)
            if session:
                user = db.get(User, session.user_id)
                if user:
                    logger.debug("Authenticated user %s via session", user.username)
                    return user

    # 2. Try API Key
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        from ..api_keys import verify_api_key
        with Session(request.app.state.db_engine) as db:
            user = verify_api_key(db, api_key_header)
            if user:
                logger.debug("Authenticated user %s via API key", user.username)
                return user

    logger.debug("No authentication found for request")
    return None



def require_auth(request: Request) -> User:
    """Require authentication, raising HTTPException if not authenticated."""
    user = get_current_user(request)
    if not user:
        # Check if it's an API request (JSON) or Browser request
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
             # Redirect to login for browser
             logger.debug("Unauthenticated browser request, raising 401")
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        else:
             logger.debug("Unauthenticated API request, raising 401")
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

def require_superuser(user: User = Depends(require_auth)) -> User:
    """Require superuser privileges."""
    if not getattr(user, "is_superuser", False):
        logger.warning("Non-superuser %s attempted superuser action", user.username)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required")
    return user

def check_permission(user: User, db: Session, action: str, resource: str) -> bool:
    """Check if a user has a specific permission via their groups."""
    if getattr(user, "is_superuser", False):
        logger.debug("Superuser %s has permission for %s on %s", user.username, action, resource)
        return True
        
    # Query: User -> UserGroup -> Group -> GroupPermission -> Permission
    # We want to see if any of the user's groups have the required permission
    stmt = (
        select(Permission)
        .join(GroupPermission, GroupPermission.permission_id == Permission.id)
        .join(UserGroup, UserGroup.group_id == GroupPermission.group_id)
        .where(UserGroup.user_id == user.id)
        .where(Permission.action == action)
        .where(Permission.resource == resource)
    )
    result = db.exec(stmt).first()
    has_perm = result is not None
    logger.debug("User %s %s permission for %s on %s", user.username, "has" if has_perm else "does not have", action, resource)
    return has_perm

def permission_dependency(action_param: str, resource: str):
    """Create a dependency that checks for specific permissions."""
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
                     logger.warning("Permission denied for user %s: %s on %s", user.username, action, resource)
                     raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, 
                        detail=f"Permission denied: {action} on {resource}"
                    )
                db.commit()  # Commit if successful
                logger.debug("Permission granted for user %s: %s on %s", user.username, action, resource)
                return user
            except Exception:
                db.rollback()  # Rollback on error
                raise
    return check