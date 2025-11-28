"""
adapt.cache
SQLite-backed cache helpers for plugins.
"""
import sqlite3
import os
import threading
import logging
from datetime import datetime, timedelta, timezone
import pickle

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '.adapt.db')
CACHE_TABLE = "cache"
_lock = threading.Lock()

def _get_conn():
    """Get a SQLite connection to the cache database."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_cache_table():
    """Initialize the cache table in the SQLite database."""
    with _lock:
        conn = _get_conn()
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
                key TEXT PRIMARY KEY,
                value BLOB,
                expires_at DATETIME,
                resource TEXT,
                user TEXT
            )
        """)
        conn.commit()
        conn.close()
    logger.debug("Cache table initialized")

def set_cache(key, value, ttl_seconds, resource, user=None):
    """Set a cache entry with a time-to-live.

    Args:
        key: The cache key.
        value: The value to cache (will be pickled).
        ttl_seconds: Time-to-live in seconds.
        resource: The resource identifier.
        user: Optional user identifier.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    blob = pickle.dumps(value)
    with _lock:
        conn = _get_conn()
        conn.execute(f"""
            INSERT OR REPLACE INTO {CACHE_TABLE} (key, value, expires_at, resource, user)
            VALUES (?, ?, ?, ?, ?)
        """, (key, blob, expires_at.isoformat(), resource, user))
        conn.commit()
        conn.close()
    logger.debug(f"Cached key '{key}' for resource '{resource}' with TTL {ttl_seconds}s, expires at {expires_at}")

def get_cache(key, resource, user=None):
    """Get a cache entry if it exists and hasn't expired.

    Args:
        key: The cache key.
        resource: The resource identifier.
        user: Optional user identifier.

    Returns:
        The cached value if found and not expired, None otherwise.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        row = conn.execute(f"""
            SELECT value, expires_at FROM {CACHE_TABLE}
            WHERE key=? AND resource=? AND (user=? OR user IS NULL)
        """, (key, resource, user)).fetchone()
        conn.close()
    if row:
        if row['expires_at'] > now:
            logger.debug(f"Cache hit for key '{key}' in resource '{resource}'")
            return pickle.loads(row['value'])
        else:
            logger.debug(f"Cache expired for key '{key}' in resource '{resource}', invalidating")
            invalidate_cache(resource, key)
    else:
        logger.debug(f"Cache miss for key '{key}' in resource '{resource}'")
    return None

def invalidate_cache(resource, key=None):
    """Invalidate cache entries.

    Args:
        resource: The resource identifier. If None, invalidates all cache.
        key: Optional specific key to invalidate. If None, invalidates all for the resource.
    """
    with _lock:
        conn = _get_conn()
        if key:
            conn.execute(f"DELETE FROM {CACHE_TABLE} WHERE resource=? AND key=?", (resource, key))
        elif resource:
            conn.execute(f"DELETE FROM {CACHE_TABLE} WHERE resource=?", (resource,))
        else:
            conn.execute(f"DELETE FROM {CACHE_TABLE}")
        conn.commit()
        conn.close()
    if key:
        logger.debug(f"Invalidated cache key '{key}' for resource '{resource}'")
    elif resource:
        logger.debug(f"Invalidated all cache for resource '{resource}'")
    else:
        logger.debug("Invalidated entire cache")

def list_cache(resource=None):
    """List cache entries.

    Args:
        resource: Optional resource filter.

    Returns:
        List of cache entry dictionaries.
    """
    logger.debug(f"Listing cache entries for resource: {resource}")
    with _lock:
        conn = _get_conn()
        if resource:
            rows = conn.execute(f"SELECT * FROM {CACHE_TABLE} WHERE resource=?", (resource,)).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {CACHE_TABLE}").fetchall()
        conn.close()
    return [dict(row) for row in rows]

init_cache_table()
