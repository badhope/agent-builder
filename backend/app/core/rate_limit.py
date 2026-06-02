"""Rate limiter (slowapi + Redis)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.settings import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=str(_settings.redis.url) if _settings.rate_limit.storage_backend == "redis" else "memory://",
    default_limits=[_settings.rate_limit.default],
    headers_enabled=True,
    strategy="fixed-window",
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a structured 429 response that matches our error envelope."""
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=429,
        content={
            "code": "rate_limited",
            "message": f"Rate limit exceeded: {exc.detail}",
            "details": {"limit": str(exc.detail)},
            "request_id": getattr(request.state, "request_id", None),
        },
        headers={"Retry-After": str(int(retry_after))},
    )


__all__ = ["limiter", "rate_limit_exceeded_handler"]
