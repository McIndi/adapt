from pathlib import Path
import logging

from sqlmodel import Session, select

from ...config import AdaptConfig
from ...storage import Group, init_database

logger = logging.getLogger(__name__)


def run_create_group(root: Path, name: str, description: str | None = None) -> None:
    """Create a group."""
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)

    with Session(engine) as db:
        existing = db.exec(select(Group).where(Group.name == name)).first()
        if existing:
            logger.warning("Group '%s' already exists", name)
            print(f"Group '{name}' already exists")
            return

        group = Group(name=name, description=description)
        db.add(group)
        db.commit()

    logger.info("Created group '%s'", name)
    print(f"Created group '{name}'")
