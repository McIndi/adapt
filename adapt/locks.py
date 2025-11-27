from __future__ import annotations

import datetime
from datetime import timezone
from typing import Optional
import time

from sqlmodel import Session, select, delete
from sqlalchemy.exc import IntegrityError

from .storage import LockRecord

class LockManager:
    """Simple file‑level lock manager using the `LockRecord` table.
    It provides acquire/release semantics and a context‑manager helper.
    """

    def __init__(self, db_engine):
        self.db_engine = db_engine

    def acquire_lock(self, resource: str, owner: str, reason: Optional[str] = None, ttl_seconds: int = 300) -> LockRecord:
        """Create a lock for *resource*.
        If a lock already exists and is not expired, an exception is raised.
        """
        now = datetime.datetime.now(tz=timezone.utc)
        expires = now + datetime.timedelta(seconds=ttl_seconds)
        
        with Session(self.db_engine) as db:
            try:
                # Try to insert directly (optimistic)
                lock = LockRecord(resource=resource, owner=owner, acquired_at=now, expires_at=expires, reason=reason)
                db.add(lock)
                db.commit()
                db.refresh(lock)
                return lock
            except IntegrityError:
                db.rollback()
                # Lock exists, check if expired
                existing = db.exec(select(LockRecord).where(LockRecord.resource == resource)).first()
                if existing and (existing.expires_at is None or existing.expires_at.replace(tzinfo=timezone.utc) > now):
                    raise RuntimeError(f"Resource '{resource}' is already locked by {existing.owner}")
                else:
                    # Expired lock, delete and retry
                    db.delete(existing)
                    db.commit()
                    return self.acquire_lock(resource, owner, reason, ttl_seconds)

    def release_lock(self, lock_id: int) -> bool:
        """Release the lock with *lock_id*; returns True if a lock was deleted."""
        with Session(self.db_engine) as db:
            stmt = delete(LockRecord).where(LockRecord.id == lock_id)
            result = db.exec(stmt)
            db.commit()
            return result.rowcount > 0

    def check_lock(self, resource: str) -> Optional[LockRecord]:
        """Return the active lock for *resource* or None if unlocked/expired."""
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
        cutoff = datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(seconds=max_age_seconds)
        with Session(self.db_engine) as db:
            stmt = delete(LockRecord).where(LockRecord.acquired_at < cutoff)
            result = db.exec(stmt)
            db.commit()
            return result.rowcount

    # Context manager helper
    class _LockContext:
        def __init__(self, manager: "LockManager", resource: str, owner: str, reason: Optional[str] = None, timeout_seconds: int = 30):
            self.manager = manager
            self.resource = resource
            self.owner = owner
            self.reason = reason
            self.timeout_seconds = timeout_seconds
            self.lock: Optional[LockRecord] = None

        def __enter__(self):
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
            if self.lock:
                self.manager.release_lock(self.lock.id)
            return False

    def lock(self, resource: str, owner: str, reason: Optional[str] = None, timeout_seconds: int = 30):
        """Return a context manager for `with lock_manager.lock(...):` usage."""
        return self._LockContext(self, resource, owner, reason, timeout_seconds)
