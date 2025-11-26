from pathlib import Path

from ..config import AdaptConfig
from ..discovery import discover_resources
from ..storage import init_database


def run_check(root: Path) -> None:
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    resources = discover_resources(config.root, config)
    count = len(resources)
    print(f"Document root: {config.root}")
    print(f"SQLite store: {config.db_path} (engine {engine})")
    print(f"Discovered {count} dataset(s)")