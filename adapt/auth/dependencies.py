from fastapi import Request, HTTPException, status, Depends
from sqlmodel import Session

from ..storage import User, UserGroup, GroupPermission, Permission

def get_current_user(request: Request) -> User | None:
    # 1. Try Session Cookie
    from .session import get_session
    token = request.cookies.get("adapt_session")
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
        from ..api_keys import verify_api_key
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