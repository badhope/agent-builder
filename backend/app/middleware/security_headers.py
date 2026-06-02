"""Static security headers.

Sane defaults for an API server. The HSTS header is only emitted in
production (i.e. when ``APP_ENV=prod``) or when explicitly enabled.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.settings import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject a baseline of security response headers on every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        s = get_settings()

        # Common hardening headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", s.security_headers.referrer_policy)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        response.headers.setdefault("X-DNS-Prefetch-Control", "off")
        response.headers.setdefault("X-Download-Options", "noopen")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        # Don't cache API responses by default
        if request.url.path.startswith("/v1/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"

        # HSTS only in production
        if s.is_production or s.security_headers.hsts_enabled:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={s.security_headers.hsts_max_age}; includeSubDomains",
            )
        return response


__all__ = ["SecurityHeadersMiddleware"]
