import argparse
from pathlib import Path

from .list_resources import run_list_resources
from .create_permissions import run_create_permissions
from .list_groups import run_list_groups


def run_admin(args):
    """Run admin subcommands."""
    if args.admin_command == "list-resources":
        run_list_resources(Path(args.root).resolve())
    elif args.admin_command == "create-permissions":
        run_create_permissions(
            root=Path(args.root).resolve(),
            resources=args.resources,
            all_group_name=args.all_group,
            read_group_name=args.read_group
        )
    elif args.admin_command == "list-groups":
        run_list_groups(Path(args.root).resolve())