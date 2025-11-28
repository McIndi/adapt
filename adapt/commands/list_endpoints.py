from pathlib import Path
import logging

from ..config import AdaptConfig
from ..discovery import discover_resources

logger = logging.getLogger(__name__)


def run_list_endpoints(root: Path) -> None:
    """List all discovered API endpoints.

    Args:
        root: The root directory path for the Adapt configuration.

    Returns:
        None

    Raises:
        None
    """
    config = AdaptConfig(root=root)
    resources = discover_resources(config.root, config)
    if not resources:
        logger.info("No resources discovered in root %s", config.root)
        print("No resources discovered.")
        return

    logger.debug("Listing endpoints for %d resources", len(resources))
    for resource in resources:
        namespace = resource.relative_path.with_suffix("").as_posix()
        if resource.resource_type not in ("html", "markdown"):
            print(f"/api/{namespace}")
            print(f"/ui/{namespace}")
            print(f"/schema/{namespace}")
        else:
            print(f"/{namespace}")