"""Per-request UUID stored on ``request.state.request_id`` and echoed
in the ``X-Request-ID`` response header."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestIdMiddleware(BaseHTTPMiddleware):
    HEADER_IN = "X-Request-ID"
    HEADER_OUT = "X-Request-ID"

    def __init__(self, app: ASGIApp, *, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self.HEADER_IN = header_name
        self.HEADER_OUT = header_name

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get(self.HEADER_IN) or uuid.uuid4().hex
        request.state.request_id = rid
        response: Response = await call_next(request)
        response.headers[self.HEADER_OUT] = rid
        return response


__all__ = ["RequestIdMiddleware"]
