from pathlib import Path
import logging

from ...admin.resources import list_resources

logger = logging.getLogger(__name__)


def run_list_resources(root: Path) -> None:
    """List all discovered resources."""
    resources = list_resources(root)
    if not resources:
        logger.info("No resources discovered in root %s", root)
        print("No resources discovered.")
        return
    
    logger.debug("Listing %d discovered resources", len(resources))
    print("Discovered resources:")
    for resource in sorted(resources):
        print(f"  {resource}")