from fastapi import Depends, HTTPException, Request, Query
from sqlmodel import Session, select
from typing import List
import logging

from ..auth import require_superuser, hash_password
from ..storage import User, get_db_session
from ..audit import log_action
from . import router
from .models import UserCreate, UserPublic

logger = logging.getLogger(__name__)

@router.get("/users", response_model=List[UserPublic])
def list_users(
    db: Session = Depends(get_db_session),
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(username|created_at|is_active|is_superuser)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    filter: str = None,
    user: User = Depends(require_superuser)
):
    """List all users with optional query parameters."""
    from ..utils.query import apply_filter, apply_sort, apply_pagination
    import json
    
    query = select(User)
    users = db.exec(query).all()
    
    # Convert to dicts for filtering/sorting
    user_dicts = []
    for u in users:
        user_dicts.append({
            "id": u.id,
            "username": u.username,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "created_at": u.created_at.isoformat() if u.created_at else None
        })
    
    # Apply filters
    if filter:
        filter_dict = json.loads(filter)
        user_dicts = apply_filter(user_dicts, filter_dict)
    
    # Apply sorting
    if sort:
        user_dicts = apply_sort(user_dicts, sort, order)
    
    # Apply pagination
    user_dicts = apply_pagination(user_dicts, offset, limit)
    
    # Convert back to User objects
    result = []
    for ud in user_dicts:
        u = db.get(User, ud["id"])
        if u:
            result.append(u)
    
    logger.debug("Listed %d users with query params", len(result))
    return [
        UserPublic(
            id=u.id,
            username=u.username,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            created_at=u.created_at,
        )
        for u in result
    ]

@router.post("/users", response_model=UserPublic)
def create_user(user_data: UserCreate, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    """Create a new user."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        from fastapi import HTTPException
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    existing = db.exec(select(User).where(User.username == user_data.username)).first()
    if existing:
        logger.warning("Attempted to create user with existing username %s", user_data.username)
        raise HTTPException(status_code=400, detail="User already exists")
    
    new_user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        is_superuser=user_data.is_superuser,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    log_action(request, "create_user", "user", f"Created user {new_user.username}", user.id)
    logger.info("Created user %s", new_user.username)
    
    return UserPublic(
        id=new_user.id,
        username=new_user.username,
        is_active=new_user.is_active,
        is_superuser=new_user.is_superuser,
        created_at=new_user.created_at,
    )

@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    """Delete a user by ID."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        from fastapi import HTTPException
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    target = db.get(User, user_id)
    if not target:
        logger.warning("Attempted to delete non-existent user %d", user_id)
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        logger.warning("User %s attempted to delete themselves", user.username)
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    db.delete(target)
    db.commit()
    
    log_action(request, "delete_user", "user", f"Deleted user {target.username}", user.id)
    logger.info("Deleted user %s", target.username)
    
    return {"success": True}