from fastapi import Depends, HTTPException, Request, Query
from sqlmodel import Session, select
from typing import List
import logging

from ..auth import require_superuser
from ..storage import User, Group, UserGroup, get_db_session
from ..audit import log_action
from . import router
from .models import GroupCreate, GroupRead

logger = logging.getLogger(__name__)

@router.get("/groups", response_model=List[Group])
def list_groups(
    db: Session = Depends(get_db_session),
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(name|description)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List all groups with optional query parameters."""
    from ..utils.query import apply_filter, apply_sort, apply_pagination
    import json
    
    groups = db.exec(select(Group)).all()
    
    # Convert to dicts
    group_dicts = []
    for g in groups:
        group_dicts.append({
            "id": g.id,
            "name": g.name,
            "description": g.description
        })
    
    # Apply filters
    if filter:
        filter_dict = json.loads(filter)
        group_dicts = apply_filter(group_dicts, filter_dict)
    
    # Apply sorting
    if sort:
        group_dicts = apply_sort(group_dicts, sort, order)
    
    # Apply pagination
    group_dicts = apply_pagination(group_dicts, offset, limit)
    
    # Convert back to Group objects
    result = []
    for gd in group_dicts:
        g = db.get(Group, gd["id"])
        if g:
            result.append(g)
    
    logger.debug("Listed %d groups with query params", len(result))
    return result

@router.get("/groups/{group_id}", response_model=GroupRead)
def get_group(group_id: int, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Get a group by ID, including its users."""
    group = db.get(Group, group_id)
    if not group:
        logger.warning("Attempted to get non-existent group %d", group_id)
        raise HTTPException(status_code=404, detail="Group not found")
    # Manually load users since it's a many-to-many relationship
    # Note: SQLModel should handle this if configured correctly, but let's be explicit
    # We need to join UserGroup and User
    stmt = select(User).join(UserGroup).where(UserGroup.group_id == group_id)
    users = db.exec(stmt).all()
    
    logger.debug("Retrieved group %s with %d users", group.name, len(users))
    return GroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        users=users
    )

@router.post("/groups", response_model=Group)
def create_group(group_data: GroupCreate, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Create a new group."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    existing = db.exec(select(Group).where(Group.name == group_data.name)).first()
    if existing:
        logger.warning("Attempted to create group with existing name %s", group_data.name)
        raise HTTPException(status_code=400, detail="Group already exists")
    
    group = Group(name=group_data.name, description=group_data.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    
    log_action(request, "create_group", "group", f"Created group {group.name}", user.id)
    logger.info("Created group %s", group.name)
    
    return group

@router.delete("/groups/{group_id}")
def delete_group(group_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Delete a group by ID."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    group = db.get(Group, group_id)
    if not group:
        logger.warning("Attempted to delete non-existent group %d", group_id)
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    
    log_action(request, "delete_group", "group", f"Deleted group {group.name}", user.id)
    logger.info("Deleted group %s", group.name)
    
    return {"success": True}

@router.post("/groups/{group_id}/users/{user_id}")
def add_user_to_group(group_id: int, user_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Add a user to a group."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    # Check existence
    target_user = db.get(User, user_id)
    target_group = db.get(Group, group_id)
    if not target_user or not target_group:
         logger.warning("Attempted to add user %d to group %d: user or group not found", user_id, group_id)
         raise HTTPException(status_code=404, detail="User or Group not found")
         
    link = db.get(UserGroup, (user_id, group_id))
    if link:
        logger.debug("User %s already in group %s", target_user.username, target_group.name)
        return {"success": True} # Already member
        
    link = UserGroup(user_id=user_id, group_id=group_id)
    db.add(link)
    db.commit()
    log_action(request, "add_user_to_group", "group", f"Added user {target_user.username} to group {target_group.name}", user.id)
    logger.info("Added user %s to group %s", target_user.username, target_group.name)
    return {"success": True}

@router.delete("/groups/{group_id}/users/{user_id}")
def remove_user_from_group(group_id: int, user_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Remove a user from a group."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    target_user = db.get(User, user_id)
    target_group = db.get(Group, group_id)
    if not target_user or not target_group:
         logger.warning("Attempted to remove user %d from group %d: user or group not found", user_id, group_id)
         raise HTTPException(status_code=404, detail="User or Group not found")

    link = db.get(UserGroup, (user_id, group_id))
    if link:
        db.delete(link)
        db.commit()
        log_action(request, "remove_user_from_group", "group", f"Removed user {target_user.username} from group {target_group.name}", user.id)
        logger.info("Removed user %s from group %s", target_user.username, target_group.name)
    else:
        logger.debug("User %s not in group %s", target_user.username, target_group.name)
    return {"success": True}