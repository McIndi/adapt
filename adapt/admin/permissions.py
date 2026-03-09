from fastapi import Depends, HTTPException, Request, Query
from sqlmodel import Session, select
from typing import List
import logging

from ..auth import require_superuser
from ..storage import Permission, Group, GroupPermission, get_db_session
from ..audit import log_action
from . import router
from .models import PermissionCreate

logger = logging.getLogger(__name__)

@router.get("/permissions", response_model=List[Permission])
def list_permissions(
    db: Session = Depends(get_db_session),
    limit: int = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query(None, pattern="^(id|resource|action|description)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    filter: str = None,
    user = Depends(require_superuser)
):
    """List all permissions with optional query parameters."""
    from ..utils.query import apply_filter, apply_sort, apply_pagination
    import json
    
    permissions = db.exec(select(Permission)).all()
    
    # Convert to dicts for filtering/sorting
    perm_dicts = []
    for p in permissions:
        perm_dicts.append({
            "id": p.id,
            "resource": p.resource,
            "action": p.action.value if hasattr(p.action, 'value') else str(p.action),  # Handle enum
            "description": p.description
        })
    
    # Apply filters
    if filter:
        filter_dict = json.loads(filter)
        perm_dicts = apply_filter(perm_dicts, filter_dict)
    
    # Apply sorting
    if sort:
        perm_dicts = apply_sort(perm_dicts, sort, order)
    
    # Apply pagination
    perm_dicts = apply_pagination(perm_dicts, offset, limit)
    
    # Convert back to Permission objects
    result = []
    for pd in perm_dicts:
        p = db.get(Permission, pd["id"])
        if p:
            result.append(p)
    
    logger.debug("Listed %d permissions with query params", len(result))
    return result

@router.post("/permissions", response_model=Permission)
def create_permission(perm_data: PermissionCreate, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Create a new permission."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    existing = db.exec(select(Permission).where(
        Permission.resource == perm_data.resource,
        Permission.action == perm_data.action
    )).first()
    if existing:
        logger.warning("Attempted to create duplicate permission: %s on %s", perm_data.action, perm_data.resource)
        raise HTTPException(status_code=400, detail="Permission already exists")
    
    perm = Permission(
        resource=perm_data.resource,
        action=perm_data.action,
        description=perm_data.description
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    
    log_action(request, "create_permission", "permission", f"Created permission {perm.action} on {perm.resource}", user.id)
    logger.info("Created permission %s on %s", perm.action, perm.resource)
    
    return perm

@router.delete("/permissions/{perm_id}")
def delete_permission(perm_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Delete a permission by ID."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    perm = db.get(Permission, perm_id)
    if not perm:
        logger.warning("Attempted to delete non-existent permission %d", perm_id)
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
    
    log_action(request, "delete_permission", "permission", f"Deleted permission {perm.action} on {perm.resource}", user.id)
    logger.info("Deleted permission %s on %s", perm.action, perm.resource)
    
    return {"success": True}

@router.get("/groups/{group_id}/permissions", response_model=List[Permission])
def list_group_permissions(group_id: int, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """List permissions assigned to a group."""
    stmt = (
        select(Permission)
        .join(GroupPermission)
        .where(GroupPermission.group_id == group_id)
    )
    permissions = db.exec(stmt).all()
    logger.debug("Listed %d permissions for group %d", len(permissions), group_id)
    return permissions

@router.post("/groups/{group_id}/permissions/{perm_id}")
def add_permission_to_group(group_id: int, perm_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Add a permission to a group."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    target_group = db.get(Group, group_id)
    target_permission = db.get(Permission, perm_id)
    if not target_group or not target_permission:
        logger.warning("Attempted to add permission %d to group %d: group or permission not found", perm_id, group_id)
        raise HTTPException(status_code=404, detail="Group or Permission not found")
        
    link = db.get(GroupPermission, (group_id, perm_id))
    if link:
        logger.debug("Permission %s on %s already assigned to group %s", target_permission.action, target_permission.resource, target_group.name)
        return {"success": True}
        
    link = GroupPermission(group_id=group_id, permission_id=perm_id)
    db.add(link)
    db.commit()
    log_action(request, "add_permission_to_group", "group_permission", f"Added permission {target_permission.action} on {target_permission.resource} to group {target_group.name}", user.id)
    logger.info("Added permission %s on %s to group %s", target_permission.action, target_permission.resource, target_group.name)
    return {"success": True}

@router.delete("/groups/{group_id}/permissions/{perm_id}")
def remove_permission_from_group(group_id: int, perm_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    """Remove a permission from a group."""
    # Check if server is in read-only mode
    if request.app.state.config.readonly:
        raise HTTPException(status_code=405, detail="Server is in read-only mode")
    
    target_group = db.get(Group, group_id)
    target_permission = db.get(Permission, perm_id)
    if not target_group or not target_permission:
        logger.warning("Attempted to remove permission %d from group %d: group or permission not found", perm_id, group_id)
        raise HTTPException(status_code=404, detail="Group or Permission not found")

    link = db.get(GroupPermission, (group_id, perm_id))
    if not link:
        logger.warning("Attempted to remove unassigned permission %d from group %d", perm_id, group_id)
        raise HTTPException(status_code=404, detail="Permission not assigned to group")
        
    db.delete(link)
    db.commit()
    log_action(request, "remove_permission_from_group", "group_permission", f"Removed permission {target_permission.action} on {target_permission.resource} from group {target_group.name}", user.id)
    logger.info("Removed permission %s on %s from group %s", target_permission.action, target_permission.resource, target_group.name)
    return {"success": True}