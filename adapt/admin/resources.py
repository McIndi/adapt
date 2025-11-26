from pathlib import Path
from typing import List

from ..config import AdaptConfig
from ..discovery import discover_resources


def list_resources(root: Path) -> List[str]:
    """List all discovered resources from the root directory.
    
    Returns a list of resource identifiers (relative paths without extensions).
    """
    config = AdaptConfig(root=root)
    resources = discover_resources(root, config)
    return [str(r.relative_path.with_suffix("")) for r in resources]