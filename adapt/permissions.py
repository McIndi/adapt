from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from .storage import User, Permission, UserGroup, GroupPermission, init_database

class PermissionChecker:
    def __init__(self, db: Session):
        self.db = db

    def get_user_permissions(self, user: User) -> list[Permission]:
        # Direct permissions
        stmt = select(Permission).where(Permission.id.in_(
            select(UserGroup.group_id).where(UserGroup.user_id == user.id)
        ))
        # This is a simplified query; in real code you'd join tables
        direct = self.db.exec(stmt).all()
        return direct

    def has_permission(self, user: User, resource: str, action: str) -> bool:
        perms = self.get_user_permissions(user)
        for perm in perms:
            if perm.resource == resource and perm.action == action:
                return True
        return False

def require_permission(resource: str, action: str):
    def dependency(request, db: Session = Depends(lambda: request.app.state.db_engine)):
        # Retrieve current user from request (assumes auth dependency already applied)
        user = request.state.user  # set by auth middleware
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        checker = PermissionChecker(db)
        if not checker.has_permission(user, resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return True
    return dependency

def require_admin():
    def dependency(request):
        user = request.state.user
        if not user or not getattr(user, "is_superuser", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
        return True
    return dependency
