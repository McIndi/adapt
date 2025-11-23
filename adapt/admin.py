from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel import Session, select
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel

from .auth import require_superuser, hash_password, get_current_user
from .storage import User, LockRecord, Group, UserGroup, get_db_session, APIKey, AuditLog
from .locks import LockManager

router = APIRouter(prefix="/admin", tags=["admin"])

class UserCreate(BaseModel):
    username: str
    password: str
    is_superuser: bool = False

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    users: List[User] = []

@router.get("/")
def admin_ui(request: Request):
    user = get_current_user(request)
    if not user or not getattr(user, "is_superuser", False):
        return RedirectResponse(url="/auth/login?next=/admin/", status_code=302)

    # Serve the admin SPA
    static_dir = Path(__file__).parent / "static" / "admin"
    index_path = static_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(index_path)

# --- Users ---

@router.get("/users", response_model=List[User])
def list_users(db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    return db.exec(select(User)).all()

@router.post("/users", response_model=User)
def create_user(user_data: UserCreate, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    existing = db.exec(select(User).where(User.username == user_data.username)).first()
    if existing:
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
    
    from .audit import log_action
    log_action(request, "create_user", "user", f"Created user {new_user.username}", user.id)
    
    return new_user

@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    db.delete(target)
    db.commit()
    
    from .audit import log_action
    log_action(request, "delete_user", "user", f"Deleted user {target.username}", user.id)
    
    return {"success": True}

# --- Locks ---

@router.get("/locks", response_model=List[LockRecord])
def list_locks(db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    return db.exec(select(LockRecord)).all()

@router.delete("/locks/{lock_id}")
def release_lock(lock_id: int, request: Request, user: User = Depends(require_superuser)):
    manager: LockManager = request.app.state.lock_manager
    if manager.release_lock(lock_id):
        from .audit import log_action
        log_action(request, "release_lock", "lock", f"Released lock {lock_id}", user.id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Lock not found")

@router.post("/locks/clean")
def clean_stale_locks(request: Request, user: User = Depends(require_superuser)):
    manager: LockManager = request.app.state.lock_manager
    count = manager.release_stale_locks()
    from .audit import log_action
    log_action(request, "clean_stale_locks", "lock", f"Released {count} stale locks", user.id)
    return {"released": count}

# --- Groups ---

@router.get("/groups", response_model=List[Group])
def list_groups(db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    return db.exec(select(Group)).all()

@router.get("/groups/{group_id}", response_model=GroupRead)
def get_group(group_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    # Manually load users since it's a many-to-many relationship
    # Note: SQLModel should handle this if configured correctly, but let's be explicit
    # We need to join UserGroup and User
    stmt = select(User).join(UserGroup).where(UserGroup.group_id == group_id)
    users = db.exec(stmt).all()
    
    return GroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        users=users
    )

@router.post("/groups", response_model=Group)
def create_group(group_data: GroupCreate, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    existing = db.exec(select(Group).where(Group.name == group_data.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group already exists")
    
    group = Group(name=group_data.name, description=group_data.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    
    from .audit import log_action
    log_action(request, "create_group", "group", f"Created group {group.name}", user.id)
    
    return group

@router.delete("/groups/{group_id}")
def delete_group(group_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    
    from .audit import log_action
    log_action(request, "delete_group", "group", f"Deleted group {group.name}", user.id)
    
    return {"success": True}

@router.post("/groups/{group_id}/users/{user_id}")
def add_user_to_group(group_id: int, user_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    # Check existence
    target_user = db.get(User, user_id)
    target_group = db.get(Group, group_id)
    if not target_user or not target_group:
         raise HTTPException(status_code=404, detail="User or Group not found")
         
    link = db.get(UserGroup, (user_id, group_id))
    if link:
        return {"success": True} # Already member
        
    link = UserGroup(user_id=user_id, group_id=group_id)
    db.add(link)
    db.commit()
    from .audit import log_action
    log_action(request, "add_user_to_group", "group", f"Added user {target_user.username} to group {target_group.name}", user.id)
    return {"success": True}

@router.delete("/groups/{group_id}/users/{user_id}")
def remove_user_from_group(group_id: int, user_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    target_user = db.get(User, user_id)
    target_group = db.get(Group, group_id)
    if not target_user or not target_group:
         raise HTTPException(status_code=404, detail="User or Group not found")

    link = db.get(UserGroup, (user_id, group_id))
    if link:
        db.delete(link)
        db.commit()
        from .audit import log_action
        log_action(request, "remove_user_from_group", "group", f"Removed user {target_user.username} from group {target_group.name}", user.id)
    return {"success": True}

# --- Permissions ---

from .storage import Permission, GroupPermission

class PermissionCreate(BaseModel):
    resource: str
    action: str
    description: Optional[str] = None

@router.get("/permissions", response_model=List[Permission])
def list_permissions(db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    return db.exec(select(Permission)).all()

@router.post("/permissions", response_model=Permission)
def create_permission(perm_data: PermissionCreate, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
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
    
    from .audit import log_action
    log_action(request, "create_permission", "permission", f"Created permission {perm.action} on {perm.resource}", user.id)
    
    return perm

@router.delete("/permissions/{perm_id}")
def delete_permission(perm_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    perm = db.get(Permission, perm_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
    
    from .audit import log_action
    log_action(request, "delete_permission", "permission", f"Deleted permission {perm.action} on {perm.resource}", user.id)
    
    return {"success": True}

@router.get("/groups/{group_id}/permissions", response_model=List[Permission])
def list_group_permissions(group_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    stmt = (
        select(Permission)
        .join(GroupPermission)
        .where(GroupPermission.group_id == group_id)
    )
    return db.exec(stmt).all()

@router.post("/groups/{group_id}/permissions/{perm_id}")
def add_permission_to_group(group_id: int, perm_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
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
    from .audit import log_action
    log_action(request, "add_permission_to_group", "group_permission", f"Added permission {target_permission.action} on {target_permission.resource} to group {target_group.name}", user.id)
    return {"success": True}

@router.delete("/groups/{group_id}/permissions/{perm_id}")
def remove_permission_from_group(group_id: int, perm_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    target_group = db.get(Group, group_id)
    target_permission = db.get(Permission, perm_id)
    if not target_group or not target_permission:
        raise HTTPException(status_code=404, detail="Group or Permission not found")

    link = db.get(GroupPermission, (group_id, perm_id))
    if not link:
        raise HTTPException(status_code=404, detail="Permission not assigned to group")
        
    db.delete(link)
    db.commit()
    from .audit import log_action
    log_action(request, "remove_permission_from_group", "group_permission", f"Removed permission {target_permission.action} on {target_permission.resource} from group {target_group.name}", user.id)
    return {"success": True}


# --- API Keys ---

from .api_keys import generate_api_key
from datetime import datetime, timedelta, timezone

class APIKeyCreate(BaseModel):
    user_id: int
    description: Optional[str] = None
    expires_in_days: Optional[int] = None

@router.get("/api-keys", response_model=List[APIKey])
def list_api_keys(db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    return db.exec(select(APIKey)).all()

@router.post("/api-keys")
def create_api_key(key_data: APIKeyCreate, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    target_user = db.get(User, key_data.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    raw_key, key_hash = generate_api_key()
    
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=key_data.expires_in_days)
        
    api_key = APIKey(
        user_id=key_data.user_id,
        key_hash=key_hash,
        description=key_data.description,
        expires_at=expires_at
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    from .audit import log_action
    log_action(request, "create_api_key", "api_key", f"Created API key for user {target_user.username}", user.id)
    
    # Return the raw key only once!
    return {
        "id": api_key.id,
        "key": raw_key,
        "user_id": api_key.user_id,
        "description": api_key.description,
        "expires_at": api_key.expires_at
    }

@router.delete("/api-keys/{key_id}")
def revoke_api_key(key_id: int, request: Request, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    api_key = db.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    db.delete(api_key)
    db.commit()
    
    from .audit import log_action
    log_action(request, "revoke_api_key", "api_key", f"Revoked API key {key_id}", user.id)
    
    return {"success": True}

# --- Audit Logs ---

@router.get("/audit-logs", response_model=List[AuditLog])
def list_audit_logs(db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    return db.exec(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100)).all()
