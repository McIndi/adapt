from pathlib import Path
import logging

from sqlmodel import Session, select

from ...config import AdaptConfig
from ...storage import User, init_database

logger = logging.getLogger(__name__)


def run_list_users(root: Path) -> None:
    """List all users with status flags."""
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)

    with Session(engine) as db:
        users = db.exec(select(User)).all()
        if not users:
            logger.info("No users found")
            print("No users found.")
            return

        for user in sorted(users, key=lambda u: u.username):
            flags = []
            if user.is_superuser:
                flags.append("superuser")
            if user.is_active:
                flags.append("active")
            else:
                flags.append("inactive")
            print(f"{user.username} ({', '.join(flags)})")
