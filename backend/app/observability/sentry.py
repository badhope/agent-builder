"""Sentry SDK initialisation.

Wired into the FastAPI lifespan and the Celery ``worker_ready`` signal.
If ``SENTRY_DSN`` is empty, the function is a no-op.
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.settings import get_settings

logger = get_logger(__name__)

_INITIALISED = False


def init_sentry() -> None:
    """Initialise Sentry once per process.

    Safe to call from both the FastAPI lifespan and the Celery
    ``worker_ready`` signal — the second call is a no-op.
    """
    global _INITIALISED
    if _INITIALISED:
        return
    settings = get_settings()
    dsn = settings.telemetry.sentry_dsn.get_secret_value() if settings.telemetry.sentry_dsn else ""
    if not dsn:
        logger.info("sentry.skipped", reason="no_dsn")
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.app_env.value,
            release=f"{settings.app_name}@{settings.app_version}",
            traces_sample_rate=0.05,
            profiles_sample_rate=0.0,
            integrations=[
                FastApiIntegration(),
                CeleryIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                LoggingIntegration(level=20, event_level=40),
            ],
            send_default_pii=False,
            max_breadcrumbs=50,
            attach_stacktrace=True,
        )
        _INITIALISED = True
        logger.info("sentry.initialised", dsn_host=dsn.split("@")[-1] if "@" in dsn else "custom")
    except Exception as exc:
        logger.warning("sentry.init_failed", error=str(exc))


def capture_exception(exc: BaseException, **extra: Any) -> None:
    """Best-effort exception capture; never raises."""
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            for k, v in extra.items():
                scope.set_extra(k, v)
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass


__all__ = ["capture_exception", "init_sentry"]
