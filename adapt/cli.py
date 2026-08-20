from __future__ import annotations

import sys
import argparse
import logging
import logging.config
from pathlib import Path

from .config import AdaptConfig
from .commands import check, addsuperuser, list_endpoints, reindex, serve
from .commands.admin import run_admin

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for the Adapt CLI application."""
    logger.debug("Starting Adapt CLI")
    parser = argparse.ArgumentParser(prog="adapt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start the Adapt server")
    serve_parser.add_argument("root", nargs="?", default=".", help="Document root to expose")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.add_argument("--tls-cert", help="Path to TLS certificate")
    serve_parser.add_argument("--tls-key", help="Path to TLS key")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.add_argument("--readonly", action="store_true", default=None, help="Start server in read-only mode")
    serve_parser.add_argument("--debug", action="store_true", default=None, help="Enable debug logging")

    check_parser = subparsers.add_parser("check", help="Validate config, database, and discovery")
    check_parser.add_argument("root", nargs="?", default=".", help="Document root to check")

    user_parser = subparsers.add_parser("addsuperuser", help="Create a local superuser")
    user_parser.add_argument("root", nargs="?", default=".", help="Document root containing the SQLite store")
    user_parser.add_argument("--username", required=True, help="Username for the superuser")
    user_parser.add_argument("--password", help="Password (will prompt if missing)")
    user_parser.add_argument("--password-confirm", help="Password confirmation for non-interactive use")
    user_parser.add_argument(
        "--allow-weak-password",
        action="store_true",
        help="Allow a weak password without the safety confirmation prompt",
    )

    list_parser = subparsers.add_parser("list-endpoints", help="List generated resource endpoints")
    list_parser.add_argument("root", nargs="?", default=".", help="Document root to inspect")

    reindex_parser = subparsers.add_parser("reindex", help="Rebuild the full-text search index")
    reindex_parser.add_argument("root", nargs="?", default=".", help="Document root to index")
    reindex_parser.add_argument("--force", action="store_true", help="Reindex even unchanged files")

    admin_parser = subparsers.add_parser("admin", help="Admin tasks")
    admin_subparsers = admin_parser.add_subparsers(dest="admin_command", required=True)
    admin_list_resources_parser = admin_subparsers.add_parser("list-resources", help="List discovered resources")
    admin_list_resources_parser.add_argument("root", nargs="?", default=".", help="Document root to inspect")
    
    admin_create_perms_parser = admin_subparsers.add_parser("create-permissions", help="Create permissions and groups for resources")
    admin_create_perms_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_create_perms_parser.add_argument("resources", nargs="+", help="List of resources (or '__all__' for all)")
    admin_create_perms_parser.add_argument("--all-group", default="all_resources", help="Name for the group with all permissions")
    admin_create_perms_parser.add_argument("--read-group", default="read_resources", help="Name for the group with read permissions")
    
    admin_list_groups_parser = admin_subparsers.add_parser("list-groups", help="List groups with their permissions and users")
    admin_list_groups_parser.add_argument("root", nargs="?", default=".", help="Document root")

    admin_list_users_parser = admin_subparsers.add_parser("list-users", help="List users")
    admin_list_users_parser.add_argument("root", nargs="?", default=".", help="Document root")

    admin_create_user_parser = admin_subparsers.add_parser("create-user", help="Create user")
    admin_create_user_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_create_user_parser.add_argument("--username", required=True, help="Username")
    admin_create_user_parser.add_argument("--password", help="Password (will prompt if missing)")
    admin_create_user_parser.add_argument("--password-confirm", help="Password confirmation for non-interactive use")
    admin_create_user_parser.add_argument(
        "--allow-weak-password",
        action="store_true",
        help="Allow a weak password without the safety confirmation prompt",
    )
    admin_create_user_parser.add_argument("--superuser", action="store_true", help="Create as superuser")

    admin_delete_user_parser = admin_subparsers.add_parser("delete-user", help="Delete user")
    admin_delete_user_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_delete_user_parser.add_argument("--username", required=True, help="Username")

    admin_change_password_parser = admin_subparsers.add_parser("change-password", help="Change a user password")
    admin_change_password_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_change_password_parser.add_argument("--username", required=True, help="Username")
    admin_change_password_parser.add_argument("--password", help="New password (will prompt if missing)")
    admin_change_password_parser.add_argument("--password-confirm", help="Password confirmation for non-interactive use")
    admin_change_password_parser.add_argument(
        "--allow-weak-password",
        action="store_true",
        help="Allow a weak password without the safety confirmation prompt",
    )

    admin_activate_user_parser = admin_subparsers.add_parser("activate-user", help="Activate a user")
    admin_activate_user_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_activate_user_parser.add_argument("--username", required=True, help="Username")

    admin_deactivate_user_parser = admin_subparsers.add_parser("deactivate-user", help="Deactivate a user")
    admin_deactivate_user_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_deactivate_user_parser.add_argument("--username", required=True, help="Username")

    admin_create_group_parser = admin_subparsers.add_parser("create-group", help="Create group")
    admin_create_group_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_create_group_parser.add_argument("--name", required=True, help="Group name")
    admin_create_group_parser.add_argument("--description", help="Group description")

    admin_delete_group_parser = admin_subparsers.add_parser("delete-group", help="Delete group")
    admin_delete_group_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_delete_group_parser.add_argument("--name", required=True, help="Group name")

    admin_add_to_group_parser = admin_subparsers.add_parser("add-to-group", help="Add user to group")
    admin_add_to_group_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_add_to_group_parser.add_argument("--username", required=True, help="Username")
    admin_add_to_group_parser.add_argument("--group", required=True, help="Group name")

    admin_remove_from_group_parser = admin_subparsers.add_parser("remove-from-group", help="Remove user from group")
    admin_remove_from_group_parser.add_argument("root", nargs="?", default=".", help="Document root")
    admin_remove_from_group_parser.add_argument("--username", required=True, help="Username")
    admin_remove_from_group_parser.add_argument("--group", required=True, help="Group name")

    args = parser.parse_args()
    logger.debug("Parsed CLI args: command=%s", args.command)

    # Load config early to configure logging
    root = Path(args.root) if hasattr(args, 'root') else Path('.')
    config = AdaptConfig(root=root)
    config.load_from_file()
    logging.config.dictConfig(config.logging)

    if args.command == "serve":
        logger.info("Running serve command with root=%s", args.root)
        serve.run_serve(
            root=Path(args.root).resolve(),
            host=args.host,
            port=args.port,
            tls_cert=args.tls_cert,
            tls_key=args.tls_key,
            reload=args.reload,
            readonly=args.readonly,
            debug=args.debug,
        )
    elif args.command == "check":
        logger.info("Running check command with root=%s", args.root)
        check.run_check(Path(args.root).resolve())
    elif args.command == "addsuperuser":
        logger.info("Running addsuperuser command for username=%s", args.username)
        succeeded = addsuperuser.run_add_superuser(
            Path(args.root).resolve(),
            args.username,
            args.password,
            password_confirm=args.password_confirm,
            allow_weak_password=args.allow_weak_password,
        )
        if not succeeded:
            return 1
    elif args.command == "list-endpoints":
        logger.info("Running list-endpoints command with root=%s", args.root)
        list_endpoints.run_list_endpoints(Path(args.root).resolve())
    elif args.command == "reindex":
        logger.info("Running reindex command with root=%s force=%s", args.root, args.force)
        reindex.run_reindex(Path(args.root).resolve(), force=args.force)
    elif args.command == "admin":
        logger.info("Running admin command: %s", args.admin_command)
        run_admin(args)

    return 0

if __name__ == "__main__":
    sys.exit(main())
