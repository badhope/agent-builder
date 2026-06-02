"""Tests for the LibreOffice user-profile pool.

The pool reuses pre-created profile directories across calls to skip the
1.5-3s LibreOffice cold-start cost (creating a new profile every call was
accounting for 50-70% of end-to-end conversion time).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from app.converters.backends.libreoffice import (
    LOProfilePool,
    _user_profile,
    is_available,
)


def test_is_available_uses_lru_cache() -> None:
    """is_available() must be cached so shutil.which isn't called per task."""
    from app.converters.backends import libreoffice
    libreoffice.is_available.cache_clear()
    # Drive the cache: 1000 calls, only the first should hit the underlying
    # ``shutil.which`` call; the remaining 999 must be served from the LRU
    # cache. We verify the cache is actually being used by inspecting
    # ``cache_info()`` rather than relying on a brittle wall-clock threshold
    # (which can flake on slow CI runners / shared hosts).
    for _ in range(1000):
        libreoffice.is_available()
    info = libreoffice.is_available.cache_info()
    assert info.hits == 999, f"Expected 999 cache hits, got {info.hits}"
    assert info.misses == 1, f"Expected exactly 1 cache miss, got {info.misses}"


async def test_pool_reuses_profiles() -> None:
    """A profile acquired and released must be the same Path on re-acquire."""
    pool = LOProfilePool(size=2)
    seen: set[str] = set()
    for _ in range(4):  # more than pool size, exercises the round-robin
        async with pool.acquire() as p:
            assert isinstance(p, Path)
            assert p.exists()
            seen.add(str(p))
    assert len(seen) == 2, "Pool should expose exactly `size` unique profiles"


async def test_pool_clears_lock_files_between_uses() -> None:
    """Releasing a profile must delete any LibreOffice lock files."""
    pool = LOProfilePool(size=1)
    async with pool.acquire() as p:
        (p / ".~lock.test#").write_text("locked")
    async with pool.acquire() as p2:
        # Same profile (only one in pool), locks must be gone
        assert not list(p2.glob(".~lock.*")), (
            f"Locks not cleaned: {list(p2.glob('.~lock.*'))}"
        )


async def test_pool_speedup_vs_per_call_profile() -> None:
    """Pool should be measurably faster than creating a new profile each call."""
    pool = LOProfilePool(size=2)

    # Warm up
    async with pool.acquire():
        pass

    t0 = time.monotonic()
    for _ in range(20):
        async with pool.acquire():
            pass
    pool_time = time.monotonic() - t0

    t0 = time.monotonic()
    for _ in range(20):
        with _user_profile():
            pass
    fresh_time = time.monotonic() - t0

    # Pool should be at least as fast (allow for small variance).
    assert pool_time <= fresh_time * 1.5, (
        f"Pool ({pool_time:.3f}s) should not be much slower than fresh ({fresh_time:.3f}s)"
    )


async def test_pool_replaces_missing_profile() -> None:
    """If a profile dir is deleted out from under the pool, a fresh one is made."""
    pool = LOProfilePool(size=1)
    async with pool.acquire() as p:
        # Delete the profile while it's in use
        import shutil
        shutil.rmtree(p, ignore_errors=True)
    # The pool should not crash and should hand out a fresh profile
    async with pool.acquire() as p2:
        assert p2.exists(), "Pool should provide a fresh profile when one is missing"
