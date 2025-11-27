import pytest
import threading
import time
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from adapt.locks import LockManager
from adapt.storage import LockRecord, init_database
import tempfile
from pathlib import Path


@pytest.fixture
def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    engine = init_database(db_path)
    yield engine
    engine.dispose()


@pytest.fixture
def lock_manager(db_engine):
    return LockManager(db_engine)


def test_acquire_lock_success(lock_manager):
    lock = lock_manager.acquire_lock("test.csv", "user1", "test")
    assert lock.resource == "test.csv"
    assert lock.owner == "user1"
    assert lock.reason == "test"


def test_acquire_lock_conflict(lock_manager):
    lock_manager.acquire_lock("test.csv", "user1", "test")
    with pytest.raises(RuntimeError, match="already locked"):
        lock_manager.acquire_lock("test.csv", "user2", "test")


def test_acquire_lock_expired(lock_manager):
    # Acquire with short TTL
    lock = lock_manager.acquire_lock("test.csv", "user1", "test", ttl_seconds=1)
    time.sleep(2)  # Wait for expiry
    # Should be able to acquire again
    lock2 = lock_manager.acquire_lock("test.csv", "user2", "test")
    assert lock2.owner == "user2"


def test_release_lock(lock_manager):
    lock = lock_manager.acquire_lock("test.csv", "user1", "test")
    released = lock_manager.release_lock(lock.id)
    assert released is True
    # Should be able to acquire again
    lock2 = lock_manager.acquire_lock("test.csv", "user2", "test")
    assert lock2.owner == "user2"


def test_check_lock(lock_manager):
    lock = lock_manager.acquire_lock("test.csv", "user1", "test")
    checked = lock_manager.check_lock("test.csv")
    assert checked.owner == "user1"
    lock_manager.release_lock(lock.id)
    checked = lock_manager.check_lock("test.csv")
    assert checked is None


def test_release_stale_locks(lock_manager):
    # Acquire lock
    lock = lock_manager.acquire_lock("test.csv", "user1", "test", ttl_seconds=300)
    # Manually set acquired_at to old
    with Session(lock_manager.db_engine) as db:
        lock.acquired_at = datetime.now(tz=timezone.utc) - timedelta(days=2)
        db.add(lock)
        db.commit()
    # Release stale
    cleaned = lock_manager.release_stale_locks(max_age_seconds=86400)
    assert cleaned == 1


def test_lock_context_manager(lock_manager):
    with lock_manager.lock("test.csv", "user1", "test") as lock:
        assert lock.owner == "user1"
        checked = lock_manager.check_lock("test.csv")
        assert checked is not None
    # After exit, should be released
    checked = lock_manager.check_lock("test.csv")
    assert checked is None


def test_lock_context_manager_timeout(lock_manager):
    # Acquire lock first
    lock_manager.acquire_lock("test.csv", "user1", "test")
    # Try to acquire with timeout
    with pytest.raises(TimeoutError, match="Failed to acquire lock"):
        with lock_manager.lock("test.csv", "user2", "test", timeout_seconds=1):
            pass


def test_lock_context_manager_exponential_backoff(lock_manager, monkeypatch):
    """Test that backoff delays increase exponentially."""
    # Acquire lock first
    lock_manager.acquire_lock("test.csv", "user1", "test")
    
    delays = []
    fake_time = [0]  # mutable to simulate time advancing
    def mock_time():
        return fake_time[0]
    def mock_sleep(delay):
        delays.append(delay)
        fake_time[0] += delay  # Advance fake time by delay
    
    monkeypatch.setattr(time, 'time', mock_time)
    monkeypatch.setattr(time, 'sleep', mock_sleep)
    
    # Try to acquire with timeout - use longer timeout to see multiple retries
    with pytest.raises(TimeoutError):
        with lock_manager.lock("test.csv", "user2", "test", timeout_seconds=2):
            pass
    
    # Check that delays are exponential: 0.1, 0.2, 0.4, 0.8, 1.0...
    expected = [0.1, 0.2, 0.4, 0.8, 1.0]
    assert delays == expected


def test_race_condition_prevention(lock_manager):
    """Test that race condition is prevented with unique constraint."""
    results = []
    errors = []

    def acquire_lock_thread(owner):
        try:
            lock = lock_manager.acquire_lock("test.csv", owner, "test")
            results.append(owner)
            time.sleep(0.1)  # Hold briefly
            lock_manager.release_lock(lock.id)
        except RuntimeError as e:
            errors.append(str(e))

    threads = []
    for i in range(10):
        t = threading.Thread(target=acquire_lock_thread, args=(f"user{i}",))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Only one should succeed, others should error
    assert len(results) == 1
    assert len(errors) == 9
    for error in errors:
        assert "already locked" in error


def test_unique_constraint_enforced(db_engine):
    """Test that database enforces unique constraint on resource."""
    with Session(db_engine) as db:
        lock1 = LockRecord(resource="test.csv", owner="user1", acquired_at=datetime.now(tz=timezone.utc))
        db.add(lock1)
        db.commit()
        # Try to add another with same resource
        lock2 = LockRecord(resource="test.csv", owner="user2", acquired_at=datetime.now(tz=timezone.utc))
        db.add(lock2)
        with pytest.raises(Exception):  # IntegrityError
            db.commit()