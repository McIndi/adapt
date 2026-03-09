from pathlib import Path
import logging

from sqlmodel import Session, select

from ...config import AdaptConfig
from ...storage import User, init_database

logger = logging.getLogger(__name__)


def run_delete_user(root: Path, username: str) -> None:
    """Delete a user account by username."""
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)

    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == username)).first()
        if not user:
            logger.warning("User '%s' not found", username)
            print(f"User '{username}' not found")
            return

        db.delete(user)
        db.commit()

    logger.info("Deleted user '%s'", username)
    print(f"Deleted user '{username}'")
