"""Audit middleware.

Inserts a row into the ``audit_logs`` table for every mutating
(``POST|PUT|PATCH|DELETE``) request. Failures are logged but never
propagated into the request — auditing must not break the API.
"""

from __future__ import annotations

import asyncio
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.logging_config import get_logger

logger = get_logger(__name__)

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Persist an audit row for every mutating request."""

    def __init__(self, app: ASGIApp, *, enabled: bool = True) -> None:
        super().__init__(app)
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not self._enabled or request.method not in _MUTATING:
            return await call_next(request)

        response: Response = await call_next(request)

        try:
            await asyncio.shield(self._write_audit(request, response))
        except Exception as exc:
            logger.debug("audit.middleware_failed", error=str(exc))
        return response

    async def _write_audit(self, request: Request, response: Response) -> None:
        from app.db.models.audit_log import AuditLog
        from app.db.session import get_sessionmaker

        user_id = getattr(request.state, "user_id", None)
        api_key_id = getattr(request.state, "api_key_id", None)
        rid = getattr(request.state, "request_id", None)
        ip = request.client.host if request.client else None
        ua = request.headers.get("User-Agent", "")[:500]
        try:
            sm = get_sessionmaker()
            async with sm() as session, session.begin():
                session.add(
                    AuditLog(
                        id=uuid.uuid4(),
                        actor_id=user_id,
                        actor_api_key_id=api_key_id,
                        action=f"{request.method} {request.url.path}",
                        resource_type=None,
                        resource_id=None,
                        details={
                            "status": response.status_code,
                            "query": str(request.url.query)[:512],
                        },
                        ip_address=ip,
                        user_agent=ua or None,
                        request_id=rid,
                        success=200 <= response.status_code < 400,
                    )
                )
        except Exception as exc:
            logger.debug("audit.write_failed", error=str(exc))


__all__ = ["AuditMiddleware"]
