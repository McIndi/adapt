from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import List

from ..auth import require_superuser
from ..storage import Permission, Group, GroupPermission, get_db_session
from ..audit import log_action
from . import router
from .models import PermissionCreate

@router.get("/permissions", response_model=List[Permission])
def list_permissions(db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    return db.exec(select(Permission)).all()

@router.post("/permissions", response_model=Permission)
def create_permission(perm_data: PermissionCreate, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    existing = db.exec(select(Permission).where(
        Permission.resource == perm_data.resource,
        Permission.action == perm_data.action
    )).first()
    if existing:
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
    
    return perm

@router.delete("/permissions/{perm_id}")
def delete_permission(perm_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    perm = db.get(Permission, perm_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
    
    log_action(request, "delete_permission", "permission", f"Deleted permission {perm.action} on {perm.resource}", user.id)
    
    return {"success": True}

@router.get("/groups/{group_id}/permissions", response_model=List[Permission])
def list_group_permissions(group_id: int, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    stmt = (
        select(Permission)
        .join(GroupPermission)
        .where(GroupPermission.group_id == group_id)
    )
    return db.exec(stmt).all()

@router.post("/groups/{group_id}/permissions/{perm_id}")
def add_permission_to_group(group_id: int, perm_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    target_group = db.get(Group, group_id)
    target_permission = db.get(Permission, perm_id)
    if not target_group or not target_permission:
        raise HTTPException(status_code=404, detail="Group or Permission not found")
        
    link = db.get(GroupPermission, (group_id, perm_id))
    if link:
        return {"success": True}
        
    link = GroupPermission(group_id=group_id, permission_id=perm_id)
    db.add(link)
    db.commit()
    log_action(request, "add_permission_to_group", "group_permission", f"Added permission {target_permission.action} on {target_permission.resource} to group {target_group.name}", user.id)
    return {"success": True}

@router.delete("/groups/{group_id}/permissions/{perm_id}")
def remove_permission_from_group(group_id: int, perm_id: int, request: Request, db: Session = Depends(get_db_session), user = Depends(require_superuser)):
    target_group = db.get(Group, group_id)
    target_permission = db.get(Permission, perm_id)
    if not target_group or not target_permission:
        raise HTTPException(status_code=404, detail="Group or Permission not found")

    link = db.get(GroupPermission, (group_id, perm_id))
    if not link:
        raise HTTPException(status_code=404, detail="Permission not assigned to group")
        
    db.delete(link)
    db.commit()
    log_action(request, "remove_permission_from_group", "group_permission", f"Removed permission {target_permission.action} on {target_permission.resource} from group {target_group.name}", user.id)
    return {"success": True}