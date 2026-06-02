"""FastAPI application entry point and lifespan."""

from __future__ import annotations

import contextlib
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse, Response

from app.api.v1.router import api_v1_router
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.session import dispose_engine, get_engine
from app.db.session import healthcheck as db_healthcheck
from app.exceptions import register_exception_handlers
from app.logging_config import (
    bind_contextvars,
    clear_contextvars,
    configure_logging,
    get_logger,
)
from app.middleware import (
    AuditMiddleware,
    IdempotencyMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.observability.metrics import REQUEST_LATENCY, REQUEST_TOTAL
from app.observability.sentry import init_sentry
from app.observability.tracing import init_tracing, instrument_fastapi
from app.services.auth_service import bootstrap_admin
from app.settings import get_settings
from app.storage.factory import build_storage
from app.websocket.manager import manager as ws_manager

logger = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    settings = get_settings()
    configure_logging()
    init_sentry()
    init_tracing()

    logger.info(
        "app.starting",
        env=settings.app_env,
        version=settings.app_version,
        debug=settings.app_debug,
    )

    # Build core dependencies
    _ = get_engine()
    _ = build_storage()
    _ = ws_manager  # ensures the manager is initialised

    # Bootstrap admin (no-op if already exists)
    await bootstrap_admin()

    # OpenTelemetry FastAPI instrumentation
    instrument_fastapi(app)

    logger.info("app.started")
    try:
        yield
    finally:
        logger.info("app.shutting_down")
        await ws_manager.shutdown()
        await dispose_engine()
        logger.info("app.shutdown_complete")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="DocFormatConverter API",
        version=settings.app_version,
        description=(
            "Lightweight, secure, multi-format document conversion API. "
            "Supports batch processing, async task tracking, JWT/API-Key auth, "
            "TOTP 2FA, webhook callbacks, idempotency, and audit logging."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        default_response_class=JSONResponse,
        lifespan=lifespan,
    )

    # ---- Middleware (order matters: outermost last) ----
    # 1. Trusted hosts
    if settings.api.trusted_hosts and settings.api.trusted_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.api.trusted_hosts)
    # 2. Request ID (early so all subsequent middleware can use it)
    app.add_middleware(RequestIdMiddleware)
    # 3. Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    # 4. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_allow_origins or [],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
        max_age=600,
    )
    # 5. Idempotency
    app.add_middleware(IdempotencyMiddleware, ttl_s=3600)
    # 6. Audit
    app.add_middleware(AuditMiddleware, enabled=True)
    # 7. Access log + metrics
    app.middleware("http")(_access_log_middleware)
    app.middleware("http")(_metrics_middleware)

    # ---- Rate limiter ----
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # ---- Exception handlers ----
    register_exception_handlers(app)

    # ---- Routers ----
    app.include_router(api_v1_router, prefix="/v1")
    from app.websocket.routes import router as ws_router
    app.include_router(ws_router)

    # ---- Operational endpoints (no version prefix) ----
    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "version": settings.app_version}

    @app.get("/readyz", tags=["ops"])
    async def readyz() -> dict[str, Any]:
        db_ok = await db_healthcheck()
        storage_ok = await build_storage().healthcheck()
        ok = bool(db_ok.get("ok")) and storage_ok
        return {
            "ready": ok,
            "checks": {"database": db_ok, "storage": storage_ok},
        }

    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/", tags=["ops"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs" if not settings.is_production else "disabled",
        }

    return app


# ---- Middleware implementations ----


async def _access_log_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    start = time.monotonic()
    rid = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    bind_contextvars(
        request_id=rid,
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None,
    )
    try:
        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            "http.access",
            status=response.status_code,
            duration_ms=int(elapsed),
        )
        return response
    except Exception:
        elapsed = (time.monotonic() - start) * 1000
        logger.exception("http.error", duration_ms=int(elapsed))
        raise
    finally:
        clear_contextvars()


async def _metrics_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    if not (path.startswith("/v1") or path.startswith("/ws")):
        return response
    REQUEST_LATENCY.labels(
        method=request.method, path=path, status=str(response.status_code),
    ).observe(elapsed)
    REQUEST_TOTAL.labels(
        method=request.method, path=path, status=str(response.status_code),
    ).inc()
    return response


# Module-level app for ``uvicorn app.main:app``
app = create_app()


__all__ = ["app", "create_app", "lifespan"]
