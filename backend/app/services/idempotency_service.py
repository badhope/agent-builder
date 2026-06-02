"""Idempotency-key cache.

Provides server-side deduplication of mutating requests. The middleware
(or service) calls :func:`lookup` to see if this exact
``(user, method, path, key)`` has been served recently; if so, the cached
response is replayed. New requests call :func:`reserve` to lock the key
in-flight; the worker then calls :func:`finalize` with the response once
the request completes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.idempotency import IdempotencyRecord
from app.logging_config import get_logger

logger = get_logger(__name__)


def hash_request(payload: Any) -> str:
    """Stable hash of a request body for conflict detection."""
    if isinstance(payload, bytes | bytearray):
        return hashlib.sha256(bytes(payload)).hexdigest()
    if isinstance(payload, str):
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8"),
    ).hexdigest()


class IdempotencyService:
    """Server-side dedup keyed on ``Idempotency-Key`` header."""

    DEFAULT_TTL_HOURS = 24

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lookup(
        self,
        user_id: uuid.UUID,
        method: str,
        path: str,
        key: str,
    ) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.method == method.upper(),
            IdempotencyRecord.path == path,
            IdempotencyRecord.key == key,
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if row.expires_at < datetime.now(tz=UTC):
            return None
        return row

    async def reserve(
        self,
        user_id: uuid.UUID,
        method: str,
        path: str,
        key: str,
        request_hash: str,
        *,
        ttl_s: int = 3600,
    ) -> IdempotencyRecord:
        """Insert a new record; raises ConflictError if duplicate."""
        record = IdempotencyRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            method=method.upper(),
            path=path,
            key=key,
            request_hash=request_hash,
            status_code=0,
            response_json={},
            response_headers={},
            in_flight=True,
            locked_at=datetime.now(tz=UTC),
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=ttl_s),
        )
        self.session.add(record)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise IdempotencyConflict(
                "An identical request is already in-flight or recently completed.",
                code="IDEMPOTENT_IN_FLIGHT",
            ) from exc
        return record

    async def finalize(
        self,
        record: IdempotencyRecord,
        *,
        status_code: int,
        response_body: Any,
        response_headers: dict[str, str] | None = None,
    ) -> None:
        record.status_code = int(status_code)
        record.response_json = response_body if isinstance(response_body, dict) else {"data": response_body}
        record.response_headers = response_headers or {}
        record.in_flight = False
        await self.session.flush()

    async def release(self, record: IdempotencyRecord) -> None:
        """Remove a record (e.g. when the originating request errored)."""
        await self.session.delete(record)
        await self.session.flush()


class IdempotencyConflict(Exception):
    """Raised when reserving an already-used key."""


__all__ = ["IdempotencyConflict", "IdempotencyService", "hash_request"]
