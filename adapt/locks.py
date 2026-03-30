"""adapt.locks — File-level lock manager using the LockRecord database table."""
from __future__ import annotations

import logging
import datetime
from datetime import timezone
from typing import Optional
import time

from sqlmodel import Session, select, delete
from sqlalchemy.exc import IntegrityError

from .storage import LockRecord


logger = logging.getLogger(__name__)

class LockManager:
    """Simple file‑level lock manager using the `LockRecord` table.
    It provides acquire/release semantics and a context‑manager helper.
    """

    def __init__(self, db_engine):
        """Initialize the lock manager with a database engine.

        Args:
            db_engine: The SQLAlchemy database engine.
        """
        self.db_engine = db_engine

    def acquire_lock(self, resource: str, owner: str, reason: Optional[str] = None, ttl_seconds: int = 300) -> LockRecord:
        """Create a lock for *resource*.
        If a lock already exists and is not expired, an exception is raised.
        """
        logger.info(f"Acquiring lock for resource {resource} by {owner}")
        now = datetime.datetime.now(tz=timezone.utc)
        expires = now + datetime.timedelta(seconds=ttl_seconds)
        
        with Session(self.db_engine) as db:
            try:
                # Try to insert directly (optimistic)
                lock = LockRecord(resource=resource, owner=owner, acquired_at=now, expires_at=expires, reason=reason)
                db.add(lock)
                db.commit()
                db.refresh(lock)
                logger.debug(f"Lock acquired for {resource}")
                return lock
            except IntegrityError:
                db.rollback()
                # Lock exists, check if expired
                existing = db.exec(select(LockRecord).where(LockRecord.resource == resource)).first()
                if existing and (existing.expires_at is None or existing.expires_at.replace(tzinfo=timezone.utc) > now):
                    logger.warning(f"Lock already exists for {resource} by {existing.owner}")
                    raise RuntimeError(f"Resource '{resource}' is already locked by {existing.owner}")
                else:
                    # Expired lock, delete and retry
                    db.delete(existing)
                    db.commit()
                    logger.debug(f"Expired lock removed for {resource}, retrying")
                    return self.acquire_lock(resource, owner, reason, ttl_seconds)

    def release_lock(self, lock_id: int) -> bool:
        """Release the lock with *lock_id*; returns True if a lock was deleted."""
        logger.info(f"Releasing lock {lock_id}")
        with Session(self.db_engine) as db:
            stmt = delete(LockRecord).where(LockRecord.id == lock_id)
            result = db.exec(stmt)
            db.commit()
            released = result.rowcount > 0
            logger.debug(f"Lock {lock_id} released: {released}")
            return released

    def check_lock(self, resource: str) -> Optional[LockRecord]:
        """Return the active lock for *resource* or None if unlocked/expired."""
        logger.debug(f"Checking lock for resource {resource}")
        now = datetime.datetime.now(tz=timezone.utc)
        with Session(self.db_engine) as db:
            lock = db.exec(
                select(LockRecord)
                .where(LockRecord.resource == resource)
                .where((LockRecord.expires_at == None) | (LockRecord.expires_at > now))
            ).first()
            return lock

    def release_stale_locks(self, max_age_seconds: int = 86400) -> int:
        """Delete locks older than *max_age_seconds*; returns number deleted."""
        logger.info(f"Releasing stale locks older than {max_age_seconds} seconds")
        cutoff = datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(seconds=max_age_seconds)
        with Session(self.db_engine) as db:
            stmt = delete(LockRecord).where(LockRecord.acquired_at < cutoff)
            result = db.exec(stmt)
            db.commit()
            deleted = result.rowcount
            logger.debug(f"Released {deleted} stale locks")
            return deleted

    # Context manager helper
    class _LockContext:
        """Context manager for acquiring and releasing locks."""

        def __init__(self, manager: "LockManager", resource: str, owner: str, reason: Optional[str] = None, timeout_seconds: int = 30):
            """Initialize the lock context.

            Args:
                manager: The LockManager instance.
                resource: The resource to lock.
                owner: The owner of the lock.
                reason: Optional reason for the lock.
                timeout_seconds: Timeout for acquiring the lock.
            """
            self.manager = manager
            self.resource = resource
            self.owner = owner
            self.reason = reason
            self.timeout_seconds = timeout_seconds
            self.lock: Optional[LockRecord] = None

        def __enter__(self):
            """Enter the context, acquiring the lock."""
            start = time.time()
            retry_count = 0
            while time.time() - start < self.timeout_seconds:
                try:
                    self.lock = self.manager.acquire_lock(self.resource, self.owner, self.reason)
                    return self.lock
                except RuntimeError:
                    delay = min(0.1 * (2 ** min(retry_count, 10)), 1.0)
                    time.sleep(delay)
                    retry_count += 1
            raise TimeoutError(f"Failed to acquire lock on {self.resource} after {self.timeout_seconds}s")

        def __exit__(self, exc_type, exc_val, exc_tb):
            """Exit the context, releasing the lock."""
            if self.lock:
                self.manager.release_lock(self.lock.id)
            return False

    def lock(self, resource: str, owner: str, reason: Optional[str] = None, timeout_seconds: int = 30):
        """Return a context manager for `with lock_manager.lock(...):` usage."""
        logger.debug(f"Creating lock context for {resource} by {owner}")
        return self._LockContext(self, resource, owner, reason, timeout_seconds)
