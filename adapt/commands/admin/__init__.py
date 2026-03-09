import argparse
from pathlib import Path
import logging

from .list_resources import run_list_resources
from .create_permissions import run_create_permissions
from .list_groups import run_list_groups
from .list_users import run_list_users
from .create_user import run_create_user
from .delete_user import run_delete_user
from .create_group import run_create_group
from .delete_group import run_delete_group
from .add_to_group import run_add_to_group
from .remove_from_group import run_remove_from_group

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
    elif args.admin_command == "list-users":
        logger.debug("Running admin command: list-users")
        run_list_users(Path(args.root).resolve())
    elif args.admin_command == "create-user":
        logger.debug("Running admin command: create-user for username=%s", args.username)
        run_create_user(
            root=Path(args.root).resolve(),
            username=args.username,
            password=args.password,
            is_superuser=args.superuser,
        )
    elif args.admin_command == "delete-user":
        logger.debug("Running admin command: delete-user for username=%s", args.username)
        run_delete_user(Path(args.root).resolve(), args.username)
    elif args.admin_command == "create-group":
        logger.debug("Running admin command: create-group for name=%s", args.name)
        run_create_group(Path(args.root).resolve(), args.name, args.description)
    elif args.admin_command == "delete-group":
        logger.debug("Running admin command: delete-group for name=%s", args.name)
        run_delete_group(Path(args.root).resolve(), args.name)
    elif args.admin_command == "add-to-group":
        logger.debug("Running admin command: add-to-group user=%s group=%s", args.username, args.group)
        run_add_to_group(Path(args.root).resolve(), args.username, args.group)
    elif args.admin_command == "remove-from-group":
        logger.debug("Running admin command: remove-from-group user=%s group=%s", args.username, args.group)
        run_remove_from_group(Path(args.root).resolve(), args.username, args.group)
    else:
        logger.error("Unknown admin command: %s", args.admin_command)
        raise ValueError(f"Unknown admin command: {args.admin_command}")