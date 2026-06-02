"""Idempotency middleware.

If a request carries the ``Idempotency-Key`` header:

* If we have a cached response for ``(user, method, path, key)``, replay it.
* If a request is in-flight for the same key, return 409.
* Otherwise, run the request and cache the response.

Idempotency keys are scoped to authenticated users only; unauthenticated
requests are passed through unchanged. The middleware never raises into
the request — a failure to use the cache degrades gracefully.
"""

from __future__ import annotations

import hashlib
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.logging_config import get_logger
from app.services.idempotency_service import (
    IdempotencyConflict,
    IdempotencyService,
)

logger = get_logger(__name__)

_HEADER = "Idempotency-Key"
_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, ttl_s: int = 3600) -> None:
        super().__init__(app)
        self._ttl_s = ttl_s

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method not in _METHODS:
            return await call_next(request)
        key = request.headers.get(_HEADER)
        if not key:
            return await call_next(request)
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return await call_next(request)

        from app.db.session import get_sessionmaker
        sm = get_sessionmaker()
        async with sm() as session:
            svc = IdempotencyService(session)
            existing = await svc.lookup(
                user_id, request.method, request.url.path, key,
            )
            if existing is not None and not existing.in_flight:
                # Replay cached response
                return JSONResponse(
                    status_code=existing.status_code or 200,
                    content=existing.response_json,
                    headers={
                        k: str(v) for k, v in (existing.response_headers or {}).items()
                    },
                )
            if existing is not None and existing.in_flight:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": {
                            "code": "IDEMPOTENT_IN_FLIGHT",
                            "message": "An identical request is already in flight.",
                        }
                    },
                )
            body = await request.body()
            req_hash = hashlib.sha256(body).hexdigest()
            try:
                _record = await svc.reserve(
                    user_id, request.method, request.url.path, key, req_hash,
                    ttl_s=self._ttl_s,
                )
            except IdempotencyConflict:
                return JSONResponse(
                    status_code=409,
                    content={"error": {"code": "IDEMPOTENT_IN_FLIGHT",
                                       "message": "Duplicate key."}},
                )
            await session.commit()

        # Run the request
        response = await call_next(request)
        # Cache the response
        try:
            async with sm() as session:
                svc = IdempotencyService(session)
                # Re-fetch the record
                from sqlalchemy import select

                from app.db.models.idempotency import IdempotencyRecord
                row = (
                    await session.execute(
                        select(IdempotencyRecord).where(
                            IdempotencyRecord.user_id == user_id,
                            IdempotencyRecord.method == request.method,
                            IdempotencyRecord.path == request.url.path,
                            IdempotencyRecord.key == key,
                        )
                    )
                ).scalar_one_or_none()
                if row is not None:
                    # Read body of response
                    resp_body = b""
                    async for chunk in response.body_iterator:
                        resp_body += chunk if isinstance(chunk, bytes) else chunk.encode()
                    # Reconstruct response with the consumed body
                    response = Response(
                        content=resp_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                    try:
                        content = json.loads(resp_body.decode() or "{}")
                    except Exception:
                        content = {"raw": resp_body.decode(errors="replace")[:8192]}
                    await svc.finalize(
                        row,
                        status_code=response.status_code,
                        response_body=content,
                        response_headers={k: v for k, v in response.headers.items()
                                          if k.lower() in {"content-type", "x-request-id"}},
                    )
                    await session.commit()
        except Exception as exc:
            logger.warning("idempotency.cache_failed", error=str(exc))
        return response


__all__ = ["IdempotencyMiddleware"]
