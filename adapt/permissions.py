from __future__ import annotations

import logging
from sqlmodel import Session, select

from .storage import User, Permission, UserGroup, GroupPermission


logger = logging.getLogger(__name__)

class PermissionChecker:
    """Handles permission checking for users."""

    def __init__(self, db: Session):
        """Initialize the permission checker with a database session.

        Args:
            db: The database session.
        """
        self.db = db

    def get_user_permissions(self, user: User) -> list[Permission]:
        """Get all permissions for a user through their groups.

        Args:
            user: The user to check permissions for.

        Returns:
            A list of Permission objects.
        """
        logger.debug(f"Getting permissions for user {user.username}")
        # Get permissions through groups
        stmt = select(Permission).where(Permission.id.in_(
            select(GroupPermission.permission_id).where(GroupPermission.group_id.in_(
                select(UserGroup.group_id).where(UserGroup.user_id == user.id)
            ))
        ))
        perms = self.db.exec(stmt).all()
        return perms

    def has_permission(self, user: User, resource: str, action: str) -> bool:
        """Check if a user has permission for a specific resource and action.

        Args:
            user: The user to check.
            resource: The resource name.
            action: The action (e.g., 'read', 'write').

        Returns:
            True if the user has the permission, False otherwise.
        """
        logger.debug(f"Checking permission for user {user.username} on {resource}:{action}")
        perms = self.get_user_permissions(user)
        for perm in perms:
            if perm.resource == resource and perm.action.value == action:
                return True
        return False
