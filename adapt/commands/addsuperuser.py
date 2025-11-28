import getpass
from pathlib import Path
import logging

from sqlmodel import Session, select

from ..config import AdaptConfig
from ..storage import User, init_database
from ..auth.password import hash_password

logger = logging.getLogger(__name__)


def run_add_superuser(root: Path, username: str, password: str | None) -> None:
    """Create a new superuser account.

    Args:
        root: The root directory path for the Adapt configuration.
        username: The username for the new superuser.
        password: The password for the new superuser. If None, prompts for input.

    Returns:
        None

    Raises:
        None
    """
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    if password is None:
        password = getpass.getpass("Password: ")

    hashed = hash_password(password)
    logger.debug("Hashed password for user %s", username)
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        existing = session.exec(statement).first()
        if existing:
            logger.warning("User '%s' already exists", username)
            print(f"User '{username}' already exists")
            return
        user = User(username=username, password_hash=hashed, is_active=True, is_superuser=True)
        session.add(user)
        session.commit()
        logger.info("Created superuser '%s'", username)
        print(f"Created superuser '{username}'")