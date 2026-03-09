from pathlib import Path
import logging

from sqlmodel import Session, select

from ...config import AdaptConfig
from ...storage import Group, init_database

logger = logging.getLogger(__name__)


def run_delete_group(root: Path, name: str) -> None:
    """Delete a group by name."""
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)

    with Session(engine) as db:
        group = db.exec(select(Group).where(Group.name == name)).first()
        if not group:
            logger.warning("Group '%s' not found", name)
            print(f"Group '{name}' not found")
            return

        db.delete(group)
        db.commit()

    logger.info("Deleted group '%s'", name)
    print(f"Deleted group '{name}'")
