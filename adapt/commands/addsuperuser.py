from pathlib import Path
import logging

from sqlmodel import Session, select

from ..config import AdaptConfig
from ..storage import User, init_database
from ..auth.password import hash_password
from .passwords import resolve_password

logger = logging.getLogger(__name__)


def run_add_superuser(
    root: Path,
    username: str,
    password: str | None,
    password_confirm: str | None = None,
    allow_weak_password: bool = False,
) -> bool:
    """Create a new superuser account.

    Args:
        root: The root directory path for the Adapt configuration.
        username: The username for the new superuser.
        password: The password for the new superuser. If None, prompts for input.
        password_confirm: Confirmation for non-interactive password entry.
        allow_weak_password: Allow weak passwords without an interactive override prompt.

    Returns:
        True when the command completed successfully, or False when password
        validation prevented user creation.

    Raises:
        None
    """
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    password = resolve_password(
        username=username,
        password=password,
        password_confirm=password_confirm,
        allow_weak_password=allow_weak_password,
    )
    if password is None:
        logger.warning("Aborted superuser creation for %s due to password validation", username)
        return False

    hashed = hash_password(password)
    logger.debug("Hashed password for user %s", username)
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        existing = session.exec(statement).first()
        if existing:
            logger.warning("User '%s' already exists", username)
            print(f"User '{username}' already exists")
            return True
        user = User(username=username, password_hash=hashed, is_active=True, is_superuser=True)
        session.add(user)
        session.commit()
        logger.info("Created superuser '%s'", username)
        print(f"Created superuser '{username}'")
    return True
