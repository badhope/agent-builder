"""OpenTelemetry tracing.

Initialises an OTLP gRPC or HTTP exporter when ``OTEL_ENABLED`` is true.
If no endpoint is configured, falls back to the in-memory exporter so
``tracer.start_as_current_span`` calls still work locally.
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.settings import get_settings

logger = get_logger(__name__)

_INITIALISED = False


def init_tracing(service_name: str | None = None) -> None:
    """Initialise OpenTelemetry tracing (idempotent)."""
    global _INITIALISED
    if _INITIALISED:
        return
    settings = get_settings()
    if not settings.telemetry.otel_enabled:
        logger.info("otel.skipped", reason="disabled")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        name = service_name or settings.telemetry.otel_service_name
        resource = Resource.create(
            {
                "service.name": name,
                "service.version": settings.app_version,
                "deployment.environment": settings.app_env.value,
            }
        )
        provider = TracerProvider(resource=resource)
        endpoint = settings.telemetry.otel_exporter_otlp_endpoint
        if endpoint:
            if endpoint.startswith("http://") or endpoint.startswith("https://"):
                # HTTP exporter
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
                exporter = OTLPSpanExporter(endpoint=endpoint)
            else:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )
                exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        # Always set the global provider so spans work
        trace.set_tracer_provider(provider)
        # Auto-instrument FastAPI / SQLAlchemy / Celery / Redis if available
        _auto_instrument()
        _INITIALISED = True
        logger.info("otel.initialised", service=name, endpoint=endpoint or "in-memory")
    except Exception as exc:
        logger.warning("otel.init_failed", error=str(exc))


def _auto_instrument() -> None:
    """Best-effort auto-instrumentation of common libraries."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except Exception:
        FastAPIInstrumentor = None  # type: ignore
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except Exception:
        SQLAlchemyInstrumentor = None  # type: ignore
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
    except Exception:
        CeleryInstrumentor = None  # type: ignore
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
    except Exception:
        RedisInstrumentor = None  # type: ignore

    def _do() -> None:
        if CeleryInstrumentor is not None:
            try:
                CeleryInstrumentor().instrument()  # type: ignore[attr-defined]
            except Exception:
                pass
        if RedisInstrumentor is not None:
            try:
                RedisInstrumentor().instrument()  # type: ignore[attr-defined]
            except Exception:
                pass
        if SQLAlchemyInstrumentor is not None:
            try:
                from app.db.session import get_engine
                SQLAlchemyInstrumentor().instrument(  # type: ignore[attr-defined]
                    engine=get_engine().sync_engine,
                )
            except Exception:
                pass
        if FastAPIInstrumentor is not None:
            # The FastAPI app is instrumented at app creation time, not here
            pass

    # Defer until the app object exists
    import threading
    threading.Timer(0.5, _do).start()


def instrument_fastapi(app: Any) -> None:
    """Instrument a FastAPI app — call this from create_app()."""
    if not _INITIALISED:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.debug("otel.fastapi_instrumentation_failed", error=str(exc))


def get_tracer(name: str) -> Any:
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except Exception:
        return None


__all__ = ["get_tracer", "init_tracing", "instrument_fastapi"]
