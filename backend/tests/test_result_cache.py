"""Tests for the conversion-result cache.

The cache is keyed by (source_sha256, target_format, options) and stores
the storage_key of the already-converted output. On hit, the dispatcher
short-circuits the conversion pipeline and reuses the prior result.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from app.services import result_cache


class _FakeRedis:
    """Minimal async Redis stub for unit tests (no network)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def get(self, key: str) -> bytes | None:
        v = self.store.get(key)
        return v.encode() if v is not None else None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.expirations[key] = ttl

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.expirations.pop(key, None)


def _options_dict(opts: dict | None) -> str:
    return json.dumps(opts or {}, sort_keys=True, default=str)


def test_cache_key_deterministic() -> None:
    src = "a" * 64
    k1 = result_cache.make_key(src, "pdf", {"page_range": "1-3"})
    k2 = result_cache.make_key(src, "pdf", {"page_range": "1-3"})
    assert k1 == k2, "Same inputs must produce the same key"
    assert k1.startswith("docconv:result:")


def test_cache_key_changes_with_target() -> None:
    src = "a" * 64
    k1 = result_cache.make_key(src, "pdf", None)
    k2 = result_cache.make_key(src, "png", None)
    assert k1 != k2, "Different target_format must produce different keys"


def test_cache_key_changes_with_options() -> None:
    src = "a" * 64
    k1 = result_cache.make_key(src, "pdf", {"a": 1})
    k2 = result_cache.make_key(src, "pdf", {"a": 2})
    assert k1 != k2, "Different options must produce different keys"


def test_options_dict_is_stable_across_key_order() -> None:
    a = _options_dict({"a": 1, "b": 2})
    b = _options_dict({"b": 2, "a": 1})
    assert a == b, "Options dict hashing must be order-insensitive"


async def test_get_set_round_trip() -> None:
    fake = _FakeRedis()
    result_cache._set_redis_for_tests(fake)  # type: ignore[attr-defined]
    try:
        k = result_cache.make_key("z" * 64, "pdf", None)
        assert await result_cache.get_cached_output(k) is None
        await result_cache.set_cached_output(k, "uploads/x.pdf", ttl=60)
        assert await result_cache.get_cached_output(k) == "uploads/x.pdf"
    finally:
        result_cache._reset_redis_for_tests()  # type: ignore[attr-defined]


async def test_ttl_is_set_on_write() -> None:
    fake = _FakeRedis()
    result_cache._set_redis_for_tests(fake)  # type: ignore[attr-defined]
    try:
        k = result_cache.make_key("y" * 64, "pdf", None)
        await result_cache.set_cached_output(k, "uploads/y.pdf", ttl=123)
        assert fake.expirations[k] == 123
    finally:
        result_cache._reset_redis_for_tests()  # type: ignore[attr-defined]


async def test_miss_returns_none() -> None:
    fake = _FakeRedis()
    result_cache._set_redis_for_tests(fake)  # type: ignore[attr-defined]
    try:
        k = result_cache.make_key("x" * 64, "pdf", None)
        assert await result_cache.get_cached_output(k) is None
    finally:
        result_cache._reset_redis_for_tests()  # type: ignore[attr-defined]


async def test_sha256_collision_resistance() -> None:
    """Two different sources must produce different cache keys (sanity)."""
    a = hashlib.sha256(b"hello").hexdigest()
    b = hashlib.sha256(b"world").hexdigest()
    k1 = result_cache.make_key(a, "pdf", None)
    k2 = result_cache.make_key(b, "pdf", None)
    assert k1 != k2
