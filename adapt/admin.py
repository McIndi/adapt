from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel import Session, select
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel

from .auth import require_superuser, hash_password, get_current_user
from .storage import User, LockRecord, Group, UserGroup, get_db_session
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
def create_user(user_data: UserCreate, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
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
    return new_user

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    db.delete(target)
    db.commit()
    return {"success": True}

# --- Locks ---

@router.get("/locks", response_model=List[LockRecord])
def list_locks(db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    return db.exec(select(LockRecord)).all()

@router.delete("/locks/{lock_id}")
def release_lock(lock_id: int, request: Request, user: User = Depends(require_superuser)):
    manager: LockManager = request.app.state.lock_manager
    if manager.release_lock(lock_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Lock not found")

@router.post("/locks/clean")
def clean_stale_locks(request: Request, user: User = Depends(require_superuser)):
    manager: LockManager = request.app.state.lock_manager
    count = manager.release_stale_locks()
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
def create_group(group_data: GroupCreate, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    existing = db.exec(select(Group).where(Group.name == group_data.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group already exists")
    
    group = Group(name=group_data.name, description=group_data.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.delete("/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    return {"success": True}

@router.post("/groups/{group_id}/users/{user_id}")
def add_user_to_group(group_id: int, user_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    # Check existence
    if not db.get(User, user_id) or not db.get(Group, group_id):
         raise HTTPException(status_code=404, detail="User or Group not found")
         
    link = db.get(UserGroup, (user_id, group_id))
    if link:
        return {"success": True} # Already member
        
    link = UserGroup(user_id=user_id, group_id=group_id)
    db.add(link)
    db.commit()
    return {"success": True}

@router.delete("/groups/{group_id}/users/{user_id}")
def remove_user_from_group(group_id: int, user_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    link = db.get(UserGroup, (user_id, group_id))
    if link:
        db.delete(link)
        db.commit()
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
def create_permission(perm_data: PermissionCreate, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
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
    return perm

@router.delete("/permissions/{perm_id}")
def delete_permission(perm_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    perm = db.get(Permission, perm_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
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
def add_permission_to_group(group_id: int, perm_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    if not db.get(Group, group_id) or not db.get(Permission, perm_id):
        raise HTTPException(status_code=404, detail="Group or Permission not found")
        
    link = db.get(GroupPermission, (group_id, perm_id))
    if link:
        return {"success": True}
        
    link = GroupPermission(group_id=group_id, permission_id=perm_id)
    db.add(link)
    db.commit()
    return {"success": True}

@router.delete("/groups/{group_id}/permissions/{perm_id}")
def remove_permission_from_group(group_id: int, perm_id: int, db: Session = Depends(get_db_session), user: User = Depends(require_superuser)):
    link = db.get(GroupPermission, (group_id, perm_id))
    if not link:
        raise HTTPException(status_code=404, detail="Permission not assigned to group")
        
    db.delete(link)
    db.commit()
    return {"success": True}
