from pathlib import Path
from typing import List
import logging

from ..config import AdaptConfig
from ..discovery import discover_resources

logger = logging.getLogger(__name__)


def list_resources(root: Path) -> List[str]:
    """List all discovered resources from the root directory.
    
    Returns a list of resource identifiers including sub-namespaces for multi-resource files.
    """
    config = AdaptConfig(root=root)
    resources = discover_resources(root, config)
    resource_names = []
    for r in resources:
        namespace = r.relative_path.with_suffix("").as_posix()
        if "sub_namespace" in r.metadata:
            namespace += f"/{r.metadata['sub_namespace']}"
        resource_names.append(namespace)
    logger.debug("Discovered %d resources from root %s", len(resource_names), root)
    return resource_names