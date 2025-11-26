from __future__ import annotations

import argparse
from pathlib import Path

from .commands import check, addsuperuser, list_endpoints, serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="adapt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start the Adapt server")
    serve_parser.add_argument("root", nargs="?", default=".", help="Document root to expose")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--tls-cert", help="Path to TLS certificate")
    serve_parser.add_argument("--tls-key", help="Path to TLS key")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.add_argument("--readonly", action="store_true", help="Start server in read-only mode")

    check_parser = subparsers.add_parser("check", help="Validate config, database, and discovery")
    check_parser.add_argument("root", nargs="?", default=".", help="Document root to check")

    user_parser = subparsers.add_parser("addsuperuser", help="Create a local superuser")
    user_parser.add_argument("--root", default=".", help="Document root containing the SQLite store")
    user_parser.add_argument("--username", required=True, help="Username for the superuser")
    user_parser.add_argument("--password", help="Password (will prompt if missing)")

    list_parser = subparsers.add_parser("list-endpoints", help="List the auto-generated REST/UI endpoints")
    list_parser.add_argument("root", nargs="?", default=".", help="Document root to inspect")

    args = parser.parse_args()

    if args.command == "serve":
        serve.run_serve(
            root=Path(args.root).resolve(),
            host=args.host,
            port=args.port,
            tls_cert=args.tls_cert,
            tls_key=args.tls_key,
            reload=args.reload,
            readonly=args.readonly
        )
    elif args.command == "check":
        check.run_check(Path(args.root).resolve())
    elif args.command == "addsuperuser":
        addsuperuser.run_add_superuser(Path(args.root).resolve(), args.username, args.password)
    elif args.command == "list-endpoints":
        list_endpoints.run_list_endpoints(Path(args.root).resolve())
