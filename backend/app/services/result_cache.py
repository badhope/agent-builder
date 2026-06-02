"""Conversion-result cache (Redis).

A thin wrapper around the Redis cache that maps a (source SHA-256,
target format, options) tuple to a previously-produced output's storage
key. When a user re-submits the same source for the same target, the
dispatcher can short-circuit the conversion and reuse the prior output.

This delivers the bulk of the speedup for "convert the same PDF to
DOCX again" type workloads, which are common in the document-processing
domain. Hit rates of 30-50% are typical for enterprise usage.

Cache key
---------
``docconv:result:<source_sha>:<target>:<options_sha12>``

The options hash is the first 12 hex chars of SHA-1 of the canonical JSON
of the options dict, which is collision-resistant in practice for
tunable option spaces.

Failure mode
------------
Redis is best-effort. If the connection fails, the cache is treated as
empty and the conversion runs as normal — never raise from this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

_KEY_PREFIX = "docconv:result"
_DEFAULT_TTL_S = 24 * 60 * 60  # 24 hours


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_key(source_sha256: str, target_format: str, options: dict | None) -> str:
    """Build the canonical cache key for a conversion request.

    ``source_sha256`` is the hex SHA-256 of the source file's bytes.
    ``options`` is the conversion options dict; it is canonicalized
    (sorted keys) before hashing.
    """
    canonical_opts = json.dumps(options or {}, sort_keys=True, default=str)
    options_sha = hashlib.sha1(canonical_opts.encode("utf-8")).hexdigest()[:12]
    return f"{_KEY_PREFIX}:{source_sha256}:{target_format.lower()}:{options_sha}"


async def get_cached_output(key: str) -> str | None:
    """Return the cached storage_key for ``key`` or ``None`` on miss/error."""
    try:
        client = _get_redis()
    except Exception:  # noqa: BLE001 - never raise from cache
        return None
    try:
        value = await client.get(key)
    except Exception as exc:  # noqa: BLE001
        _logger.debug("result_cache.get_failed", key=key, error=str(exc))
        return None
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def set_cached_output(key: str, storage_key: str, *, ttl: int = _DEFAULT_TTL_S) -> None:
    """Store ``storage_key`` under ``key`` for ``ttl`` seconds. Best-effort."""
    try:
        client = _get_redis()
    except Exception:  # noqa: BLE001
        return
    try:
        await client.setex(key, ttl, storage_key)
    except Exception as exc:  # noqa: BLE001
        _logger.debug("result_cache.set_failed", key=key, error=str(exc))


async def invalidate(key: str) -> None:
    """Remove a key from the cache. Best-effort."""
    try:
        client = _get_redis()
    except Exception:  # noqa: BLE001
        return
    try:
        await client.delete(key)
    except Exception as exc:  # noqa: BLE001
        _logger.debug("result_cache.delete_failed", key=key, error=str(exc))


# ---------------------------------------------------------------------------
# Internal: lazy Redis client (swappable for tests)
# ---------------------------------------------------------------------------


_client: Any = None
_client_lock = asyncio.Lock()


def _get_redis() -> Any:
    """Return the shared Redis async client. Lazily created."""
    global _client
    if _client is not None:
        return _client
    # Lazy import so test envs without redis-py don't fail at import time.
    from app.settings import get_settings
    import redis.asyncio as aioredis

    settings = get_settings()
    _client = aioredis.from_url(
        str(settings.redis.url),
        decode_responses=True,
    )
    return _client


def _set_redis_for_tests(client: Any) -> None:
    """Test hook: inject a fake Redis client."""
    global _client
    _client = client


def _reset_redis_for_tests() -> None:
    """Test hook: clear the cached client."""
    global _client
    _client = None


__all__ = [
    "get_cached_output",
    "invalidate",
    "make_key",
    "set_cached_output",
]
