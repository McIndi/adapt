from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import List

from ..auth import require_superuser, hash_password
from ..storage import User, get_db_session
from ..audit import log_action
from . import router
from .models import UserCreate

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
    
    log_action(request, "delete_user", "user", f"Deleted user {target.username}", user.id)
    
    return {"success": True}