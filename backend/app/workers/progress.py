"""Progress publishing helper.

The worker pushes per-task progress events to a Redis pubsub channel;
the API process subscribes and fans the events out to any connected
WebSocket clients for that task.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis

from app.settings import get_settings

CHANNEL_PREFIX = "docconv:progress:"


def _channel(task_id: str) -> str:
    return f"{CHANNEL_PREFIX}{task_id}"


# ---------------------------------------------------------------------------
# Connection pool (module-level, lazily initialized, thread-safe)
# ---------------------------------------------------------------------------

_pool: aioredis.ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> aioredis.ConnectionPool:
    """Return the shared Redis connection pool, creating it on first use."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:  # double-check after acquiring lock
            return _pool
        settings = get_settings()
        _pool = aioredis.ConnectionPool.from_url(
            str(settings.redis.url_pubsub),
            max_connections=8,
            decode_responses=False,
        )
    return _pool


def _get_client() -> aioredis.Redis:
    """Return a Redis client backed by the shared pool."""
    return aioredis.Redis(connection_pool=_get_pool())


async def close_pool() -> None:
    """Close the connection pool (call on worker shutdown)."""
    global _pool
    pool = _pool
    _pool = None
    if pool is not None:
        try:
            await pool.disconnect(inuse_connections=True)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass


# Test hook: reset the pool between tests.
def _reset_pool_for_tests() -> None:
    global _pool
    _pool = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def publish_progress(
    *, task_id: str, user_id: str | None, payload: dict[str, Any],
) -> None:
    """Publish a progress event to the per-task channel.

    Uses a shared connection pool so high-frequency publishes do not
    re-handshake (TCP + AUTH) for each call. The previous implementation
    called ``aioredis.from_url`` + ``aclose`` on every publish, which
    wasted 0.5-2ms per call and generated noticeable CPU usage under load.
    """
    body = {
        "task_id": task_id,
        "user_id": user_id,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        **payload,
    }
    try:
        client = _get_client()
        await client.publish(_channel(task_id), json.dumps(body, default=str))
    except Exception:
        # Progress publishing is best-effort.
        pass


__all__ = [
    "CHANNEL_PREFIX",
    "close_pool",
    "publish_progress",
]
