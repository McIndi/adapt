from pathlib import Path

from ...config import AdaptConfig
from ...storage import Permission, Group, GroupPermission, init_database, Action, get_db_session, User, UserGroup
from sqlmodel import Session, select


def run_list_groups(root: Path) -> None:
    """List all groups with their permissions and assigned users."""
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    
    with Session(engine) as db:
        groups = db.exec(select(Group)).all()
        if not groups:
            print("No groups found.")
            return
        
        for group in sorted(groups, key=lambda g: g.name):
            print(f"Group: {group.name}")
            if group.description:
                print(f"  Description: {group.description}")
            
            # Get permissions
            permissions = db.exec(
                select(Permission)
                .join(GroupPermission)
                .where(GroupPermission.group_id == group.id)
            ).all()
            
            if permissions:
                print("  Permissions:")
                for perm in sorted(permissions, key=lambda p: (p.resource, p.action.value)):
                    print(f"    - {perm.action.value} on {perm.resource}")
            else:
                print("  Permissions: None")
            
            # Get users
            users = db.exec(
                select(User)
                .join(UserGroup)
                .where(UserGroup.group_id == group.id)
            ).all()
            
            if users:
                print("  Users:")
                for user in sorted(users, key=lambda u: u.username):
                    print(f"    - {user.username}")
            else:
                print("  Users: None")
            
            print()  # Blank line between groups