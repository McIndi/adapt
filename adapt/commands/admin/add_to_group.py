from pathlib import Path
import logging

from sqlmodel import Session, select

from ...config import AdaptConfig
from ...storage import Group, User, UserGroup, init_database

logger = logging.getLogger(__name__)


def run_add_to_group(root: Path, username: str, group_name: str) -> None:
    """Add a user to a group by names."""
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

        existing = db.exec(
            select(UserGroup).where(UserGroup.user_id == user.id, UserGroup.group_id == group.id)
        ).first()
        if existing:
            logger.debug("User '%s' already in group '%s'", username, group_name)
            print(f"User '{username}' is already in group '{group_name}'")
            return

        db.add(UserGroup(user_id=user.id, group_id=group.id))
        db.commit()

    logger.info("Added user '%s' to group '%s'", username, group_name)
    print(f"Added user '{username}' to group '{group_name}'")
