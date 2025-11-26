from pathlib import Path

from ...admin.resources import list_resources


def run_list_resources(root: Path) -> None:
    """List all discovered resources."""
    resources = list_resources(root)
    if not resources:
        print("No resources discovered.")
        return
    
    print("Discovered resources:")
    for resource in sorted(resources):
        print(f"  {resource}")