from pathlib import Path
import logging

from sqlmodel import Session, select

from ...config import AdaptConfig
from ...storage import Group, User, UserGroup, init_database

logger = logging.getLogger(__name__)


def run_remove_from_group(root: Path, username: str, group_name: str) -> None:
    """Remove a user from a group by names."""
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)

    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == username)).first()
        if not user:
            logger.warning("User '%s' not found", username)
            print(f"User '{username}' not found")
            return

        group = db.exec(select(Group).where(Group.name == group_name)).first()
        if not group:
            logger.warning("Group '%s' not found", group_name)
            print(f"Group '{group_name}' not found")
            return

        membership = db.exec(
            select(UserGroup).where(UserGroup.user_id == user.id, UserGroup.group_id == group.id)
        ).first()
        if not membership:
            logger.debug("User '%s' is not in group '%s'", username, group_name)
            print(f"User '{username}' is not in group '{group_name}'")
            return

        db.delete(membership)
        db.commit()

    logger.info("Removed user '%s' from group '%s'", username, group_name)
    print(f"Removed user '{username}' from group '{group_name}'")
