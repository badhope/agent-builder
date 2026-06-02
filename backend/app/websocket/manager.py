"""WebSocket connection manager with Redis pub/sub fan-out."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from typing import Any

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.logging_config import get_logger
from app.settings import get_settings

logger = get_logger(__name__)


class WebSocketManager:
    """Manages WebSocket subscriptions and forwards Redis pub/sub events."""

    def __init__(self) -> None:
        # task_id → set of (websocket, user_id)
        self._subscribers: dict[str, set[tuple[WebSocket, uuid.UUID | None]]] = (
            defaultdict(set)
        )
        # user_id → set of (websocket, task_id)
        self._by_user: dict[uuid.UUID, set[tuple[WebSocket, str | None]]] = (
            defaultdict(set)
        )
        self._lock = asyncio.Lock()
        self._redis_task: asyncio.Task | None = None
        self._redis_client: aioredis.Redis | None = None

    async def connect(
        self, websocket: WebSocket, task_id: str, user_id: uuid.UUID | None,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._subscribers[task_id].add((websocket, user_id))
            if user_id is not None:
                self._by_user[user_id].add((websocket, task_id))
        await self._ensure_listener()

    async def disconnect(
        self, websocket: WebSocket, task_id: str, user_id: uuid.UUID | None,
    ) -> None:
        async with self._lock:
            self._subscribers[task_id].discard((websocket, user_id))
            if not self._subscribers[task_id]:
                self._subscribers.pop(task_id, None)
            if user_id is not None:
                self._by_user[user_id].discard((websocket, task_id))

    async def send_personal(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    async def _ensure_listener(self) -> None:
        if self._redis_task is not None and not self._redis_task.done():
            return
        settings = get_settings()
        self._redis_client = aioredis.from_url(str(settings.redis.url_pubsub))
        self._redis_task = asyncio.create_task(self._pubsub_loop())
        logger.info("ws.listener_started")

    async def _pubsub_loop(self) -> None:
        if self._redis_client is None:
            return
        pubsub = self._redis_client.pubsub()
        await pubsub.psubscribe(f"{__import__('app.workers.progress', fromlist=['CHANNEL_PREFIX']).CHANNEL_PREFIX}*")
        try:
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                channel = message.get("channel", b"")
                if isinstance(channel, bytes):
                    channel = channel.decode()
                task_id = channel.split(":", 2)[-1]
                try:
                    data = json.loads(message["data"])
                except Exception:
                    continue
                await self._fan_out(task_id, data)
        finally:
            try:
                await pubsub.aclose()
            except Exception:
                pass

    async def _fan_out(self, task_id: str, data: dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(task_id, ()))
        dead: list[tuple[WebSocket, uuid.UUID | None]] = []
        for ws, user_id in subs:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append((ws, user_id))
        for ws, user_id in dead:
            await self.disconnect(ws, task_id, user_id)

    async def shutdown(self) -> None:
        if self._redis_task is not None:
            self._redis_task.cancel()
            try:
                await self._redis_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._redis_client is not None:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass


manager = WebSocketManager()


__all__ = ["WebSocketManager", "manager"]
