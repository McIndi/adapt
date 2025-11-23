from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from sqlalchemy import Boolean, Column, DateTime, Text
from sqlmodel import Field, SQLModel, create_engine, Session
from fastapi import Request, Depends

class LockRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    resource: str = Field(index=True, unique=True)
    owner: str
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))
    expires_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    reason: str | None = Field(default=None)

class CacheEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    resource: str = Field(index=True)
    description: str | None = None

class DBSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))
    expires_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    last_active: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    password_hash: str
    is_active: bool = Field(default=True, sa_column=Column(Boolean, default=True))
    is_superuser: bool = Field(default=False, sa_column=Column(Boolean, default=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), sa_type=DateTime(timezone=True))

class Group(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str | None = None

class Permission(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    resource: str
    action: str
    description: str | None = None

class UserGroup(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="group.id", primary_key=True)

class GroupPermission(SQLModel, table=True):
    group_id: int = Field(foreign_key="group.id", primary_key=True)
    permission_id: int = Field(foreign_key="permission.id", primary_key=True)

def init_database(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    engine_url = f"sqlite:///{path}"
    engine = create_engine(engine_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def get_db_session(request: Request) -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions with proper lifecycle management."""
    db = Session(request.app.state.db_engine)
    try:
        yield db
        db.commit()  # Commit successful operations
    except Exception:
        db.rollback()  # Rollback on error
        raise
    finally:
        db.close()  # Always cleanup