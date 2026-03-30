"""adapt.storage — SQLModel database models and engine initialization."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from sqlalchemy import Boolean, Column, DateTime, Text, UniqueConstraint, Integer, ForeignKey as SA_ForeignKey, Enum as SqlEnum
from sqlmodel import Field, SQLModel, create_engine, Session
from sqlalchemy import event
from fastapi import Request, Depends


logger = logging.getLogger(__name__)

class LockRecord(SQLModel, table=True):
    """Database model for lock records."""
    __tablename__ = "lock_records"
    id: int | None = Field(default=None, primary_key=True)
    resource: str = Field(index=True, unique=True)
    owner: str
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))
    expires_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    reason: str | None = Field(default=None)

class User(SQLModel, table=True):
    """Database model for users."""
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    password_hash: str
    is_active: bool = Field(default=True, sa_column=Column(Boolean, default=True))
    is_superuser: bool = Field(default=False, sa_column=Column(Boolean, default=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))

class Group(SQLModel, table=True):
    """Database model for groups."""
    __tablename__ = "groups"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    description: str | None = None

from enum import Enum as PyEnum


class Action(PyEnum):
    """Enumeration of possible actions."""
    read = "read"
    write = "write"


class Permission(SQLModel, table=True):
    """Database model for permissions."""
    __table_args__ = (UniqueConstraint("resource", "action"),)
    id: int | None = Field(default=None, primary_key=True)
    resource: str
    action: Action = Field(sa_column=Column(SqlEnum(Action, name="action_enum"), nullable=False))
    description: str | None = None

class UserGroup(SQLModel, table=True):
    """Database model for user-group associations."""
    user_id: int = Field(sa_column=Column(Integer, SA_ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    group_id: int = Field(sa_column=Column(Integer, SA_ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True))

class GroupPermission(SQLModel, table=True):
    """Database model for group-permission associations."""
    group_id: int = Field(sa_column=Column(Integer, SA_ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True))
    permission_id: int = Field(sa_column=Column(Integer, SA_ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True))

class APIKey(SQLModel, table=True):
    """Database model for API keys."""
    id: int | None = Field(default=None, primary_key=True)
    key_hash: str = Field(index=True, unique=True)
    user_id: int = Field(sa_column=Column(Integer, SA_ForeignKey("users.id", ondelete="CASCADE"), index=True))
    description: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))
    expires_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    last_used_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    is_active: bool = Field(default=True)

class AuditLog(SQLModel, table=True):
    """Database model for audit logs."""
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))
    # Keep logs even if users are deleted; use SET NULL to preserve audit trail
    user_id: int | None = Field(default=None, sa_column=Column(Integer, SA_ForeignKey("users.id", ondelete="SET NULL"), index=True))
    action: str = Field(index=True)
    resource: str | None = Field(default=None, index=True)
    details: str | None = None
    ip_address: str | None = None

class DBSession(SQLModel, table=True):
    """Database model for database sessions."""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(sa_column=Column(Integer, SA_ForeignKey("users.id", ondelete="CASCADE"), index=True))
    token: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))
    expires_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    last_active: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

def init_database(path: Path):
    """Initialize the database and return the engine.

    Args:
        path: The path to the database file.

    Returns:
        The SQLAlchemy engine.
    """
    logger.info(f"Initializing database at {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    engine_url = f"sqlite:///{path}"
    engine = create_engine(engine_url, connect_args={"check_same_thread": False})
    # Ensure SQLite enforces foreign key constraints for ON DELETE behaviors
    if "sqlite" in engine.url.drivername:
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    SQLModel.metadata.create_all(engine)
    return engine


def get_db_session(request: Request) -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions with proper lifecycle management."""
    logger.debug("Creating database session")
    db = Session(request.app.state.db_engine)
    try:
        yield db
        db.commit()  # Commit successful operations
        logger.debug("Committed database session")
    except Exception:
        db.rollback()  # Rollback on error
        logger.warning("Rolled back database session due to error")
        raise
    finally:
        db.close()  # Always cleanup