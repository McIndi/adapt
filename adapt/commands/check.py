from pathlib import Path
import logging

from ..config import AdaptConfig
from ..discovery import discover_resources
from ..storage import init_database

logger = logging.getLogger(__name__)


def run_check(root: Path) -> None:
    """Check the configuration and discover resources.

    Args:
        root: The root directory path for the Adapt configuration.

    Returns:
        None

    Raises:
        None
    """
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    resources = discover_resources(config.root, config)
    count = len(resources)
    logger.info("Discovered %d dataset(s) in root %s", count, config.root)
    print(f"Document root: {config.root}")
    print(f"SQLite store: {config.db_path} (engine {engine})")
    print(f"Discovered {count} dataset(s)")