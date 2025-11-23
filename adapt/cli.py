from __future__ import annotations

import argparse
import asyncio
import getpass
import hashlib
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uvicorn import Config, Server
from sqlmodel import Session, select, delete
from datetime import datetime, timezone

from .config import AdaptConfig
from .discovery import discover_resources
from .routes import generate_routes
from .storage import User, DBSession, init_database
from .locks import LockManager


from .app import create_app

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"

def serve_app(config: AdaptConfig) -> FastAPI:
    return create_app(config)


def run_check(root: Path) -> None:
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    resources = discover_resources(config.root, config)
    count = len(resources)
    print(f"Document root: {config.root}")
    print(f"SQLite store: {config.db_path} (engine {engine})")
    print(f"Discovered {count} dataset(s)")


def run_add_superuser(root: Path, username: str, password: str | None) -> None:
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    if password is None:
        password = getpass.getpass("Password: ")

    hashed = hash_password(password)
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        existing = session.exec(statement).first()
        if existing:
            print(f"User '{username}' already exists")
            return
        user = User(username=username, password_hash=hashed, is_active=True, is_superuser=True)
        session.add(user)
        session.commit()
        print(f"Created superuser '{username}'")


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
        config = AdaptConfig(root=Path(args.root).resolve(), readonly=args.readonly)
        if args.tls_cert:
            config.tls_cert = Path(args.tls_cert)
        if args.tls_key:
            config.tls_key = Path(args.tls_key)

        use_tls = bool(config.tls_cert and config.tls_key)
        config.secure_cookies = use_tls  # Set secure cookies when using TLS
        app = serve_app(config)
        server_config = Config(
            app=app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            ssl_certfile=str(config.tls_cert) if use_tls else None,
            ssl_keyfile=str(config.tls_key) if use_tls else None,
            log_level="info",
        )
        Server(config=server_config).run()
    elif args.command == "check":
        run_check(Path(args.root).resolve())
    elif args.command == "addsuperuser":
        run_add_superuser(Path(args.root).resolve(), args.username, args.password)
    elif args.command == "list-endpoints":
        run_list_endpoints(Path(args.root).resolve())
