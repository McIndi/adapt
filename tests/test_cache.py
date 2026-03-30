"""Tests for adapt.cache: configure, set_cache, get_cache, invalidate_cache, list_cache."""
import pytest
import time
import adapt.cache as cache_module


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path):
    """Give each test its own cache DB and reset module state after."""
    db_path = str(tmp_path / "cache.db")
    cache_module.configure(db_path)
    yield
    # Reset module-level state so tests don't bleed into each other
    cache_module._db_path = None


# ---------------------------------------------------------------------------
# set_cache / get_cache
# ---------------------------------------------------------------------------

def test_set_and_get_cache():
    cache_module.set_cache("k1", {"x": 1}, ttl_seconds=60, resource="res")
    result = cache_module.get_cache("k1", "res")
    assert result == {"x": 1}


def test_get_cache_miss_returns_none():
    assert cache_module.get_cache("nonexistent", "res") is None


def test_get_cache_expired_returns_none():
    cache_module.set_cache("k_exp", "val", ttl_seconds=0, resource="res")
    # TTL of 0 means expires_at == now; give a tiny sleep to ensure it's past
    time.sleep(0.05)
    assert cache_module.get_cache("k_exp", "res") is None


def test_cache_user_field_stored():
    # NOTE: the cache table uses `key TEXT PRIMARY KEY`, so two entries with
    # the same key but different users will collide (second write wins).
    # This is a known schema limitation — keys must be unique globally.
    cache_module.set_cache("k_alice", "alice_val", ttl_seconds=60, resource="res", user="alice")
    assert cache_module.get_cache("k_alice", "res", user="alice") == "alice_val"
    # The user=None (public) lookup should NOT match a user-scoped entry
    # because the WHERE clause requires user=? OR user IS NULL.
    # With user=None passed as None, the condition is: user IS NULL — alice's
    # row has user='alice', so it won't match.
    assert cache_module.get_cache("k_alice", "res", user=None) is None


def test_set_cache_overwrites_existing():
    cache_module.set_cache("k", "v1", ttl_seconds=60, resource="res")
    cache_module.set_cache("k", "v2", ttl_seconds=60, resource="res")
    assert cache_module.get_cache("k", "res") == "v2"


def test_cache_stores_various_types():
    for value in [42, 3.14, [1, 2, 3], {"a": "b"}, None, True]:
        cache_module.set_cache("typed", value, ttl_seconds=60, resource="types")
        assert cache_module.get_cache("typed", "types") == value


# ---------------------------------------------------------------------------
# invalidate_cache
# ---------------------------------------------------------------------------

def test_invalidate_specific_key():
    cache_module.set_cache("k1", "v1", ttl_seconds=60, resource="res")
    cache_module.set_cache("k2", "v2", ttl_seconds=60, resource="res")
    cache_module.invalidate_cache("res", "k1")
    assert cache_module.get_cache("k1", "res") is None
    assert cache_module.get_cache("k2", "res") == "v2"


def test_invalidate_entire_resource():
    cache_module.set_cache("k1", "v1", ttl_seconds=60, resource="res")
    cache_module.set_cache("k2", "v2", ttl_seconds=60, resource="res")
    cache_module.set_cache("other", "v3", ttl_seconds=60, resource="other_res")
    cache_module.invalidate_cache("res")
    assert cache_module.get_cache("k1", "res") is None
    assert cache_module.get_cache("k2", "res") is None
    assert cache_module.get_cache("other", "other_res") == "v3"


def test_invalidate_nonexistent_key_is_noop():
    cache_module.set_cache("k", "v", ttl_seconds=60, resource="res")
    cache_module.invalidate_cache("res", "does_not_exist")
    assert cache_module.get_cache("k", "res") == "v"


# ---------------------------------------------------------------------------
# list_cache
# ---------------------------------------------------------------------------

def test_list_cache_all():
    cache_module.set_cache("a", 1, ttl_seconds=60, resource="r1")
    cache_module.set_cache("b", 2, ttl_seconds=60, resource="r2")
    entries = cache_module.list_cache()
    assert len(entries) == 2
    keys = {e["key"] for e in entries}
    assert keys == {"a", "b"}


def test_list_cache_filtered_by_resource():
    cache_module.set_cache("a", 1, ttl_seconds=60, resource="r1")
    cache_module.set_cache("b", 2, ttl_seconds=60, resource="r2")
    entries = cache_module.list_cache("r1")
    assert len(entries) == 1
    assert entries[0]["key"] == "a"


def test_list_cache_empty():
    assert cache_module.list_cache() == []
