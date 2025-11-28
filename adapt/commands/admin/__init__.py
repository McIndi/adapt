import argparse
from pathlib import Path
import logging

from .list_resources import run_list_resources
from .create_permissions import run_create_permissions
from .list_groups import run_list_groups

logger = logging.getLogger(__name__)


def run_admin(args):
    """Run admin subcommands.

    Args:
        args: Parsed command-line arguments containing the admin command and options.

    Returns:
        None

    Raises:
        ValueError: If an unknown admin command is provided.
    """
    if args.admin_command == "list-resources":
        logger.debug("Running admin command: list-resources")
        run_list_resources(Path(args.root).resolve())
    elif args.admin_command == "create-permissions":
        logger.debug("Running admin command: create-permissions with resources %s", args.resources)
        run_create_permissions(
            root=Path(args.root).resolve(),
            resources=args.resources,
            all_group_name=args.all_group,
            read_group_name=args.read_group
        )
    elif args.admin_command == "list-groups":
        logger.debug("Running admin command: list-groups")
        run_list_groups(Path(args.root).resolve())
    else:
        logger.error("Unknown admin command: %s", args.admin_command)
        raise ValueError(f"Unknown admin command: {args.admin_command}")