from pathlib import Path

from ..config import AdaptConfig
from ..discovery import discover_resources


def run_list_endpoints(root: Path) -> None:
    config = AdaptConfig(root=root)
    resources = discover_resources(config.root, config)
    if not resources:
        print("No resources discovered.")
        return

    for resource in resources:
        namespace = resource.relative_path.with_suffix("").as_posix()
        if resource.resource_type not in ("html", "markdown"):
            print(f"/api/{namespace}")
            print(f"/ui/{namespace}")
            print(f"/schema/{namespace}")
        else:
            print(f"/{namespace}")