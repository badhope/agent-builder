"""Celery application factory."""

from __future__ import annotations

from typing import Any

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.logging_config import configure_logging, get_logger
from app.settings import get_settings

logger = get_logger(__name__)

_settings = get_settings()


def _build_celery() -> Celery:
    app = Celery(
        "docconverter",
        broker=str(_settings.redis.url_celery),
        backend=str(_settings.redis.url),
        include=[
            "app.workers.conversion",
            "app.workers.cleanup",
            "app.workers.webhook",
            "app.workers.maintenance",
        ],
    )
    app.conf.update(
        # Serialisation
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        result_extended=True,
        # Timezone
        timezone="UTC",
        enable_utc=True,
        # Reliability
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        # Pacing
        worker_prefetch_multiplier=_settings.worker.prefetch_multiplier,
        worker_concurrency=_settings.worker.concurrency,
        task_time_limit=_settings.worker.task_time_limit_s,
        task_soft_time_limit=_settings.worker.task_soft_time_limit_s,
        # Routing
        task_default_queue="default",
        task_routes={
            "app.workers.conversion.*": {"queue": "conversion"},
            "app.workers.cleanup.*": {"queue": "maintenance"},
            "app.workers.webhook.*": {"queue": "notifications"},
            "app.workers.maintenance.*": {"queue": "maintenance"},
        },
        # Beat schedule
        beat_schedule={
            "expire-old-tasks": {
                "task": "app.workers.cleanup.expire_old_tasks",
                "schedule": 300.0,  # 5 min
            },
            "deliver-pending-webhooks": {
                "task": "app.workers.webhook.deliver_pending",
                "schedule": 15.0,
            },
            "purge-expired-files": {
                "task": "app.workers.cleanup.purge_expired_files",
                "schedule": 600.0,  # 10 min
            },
            "purge-idempotency": {
                "task": "app.workers.cleanup.purge_idempotency_records",
                "schedule": 3600.0,  # 1h
            },
            "requeue-stuck-tasks": {
                "task": "app.workers.cleanup.requeue_stuck_tasks",
                "schedule": 300.0,  # 5 min
            },
            "refresh-metrics": {
                "task": "app.workers.cleanup.refresh_metrics",
                "schedule": 60.0,
            },
            "storage-quotas": {
                "task": "app.workers.maintenance.recompute_storage_quotas",
                "schedule": 1800.0,  # 30 min
            },
            "orphan-files": {
                "task": "app.workers.maintenance.detect_orphan_files",
                "schedule": 3600.0,
            },
        },
    )
    return app


celery_app: Celery = _build_celery()


@worker_ready.connect
def _on_worker_ready(**_: Any) -> None:  # pragma: no cover
    configure_logging()
    logger.info("worker.ready", concurrency=celery_app.conf.worker_concurrency)


@worker_shutdown.connect
def _on_worker_shutdown(**_: Any) -> None:  # pragma: no cover
    logger.info("worker.shutdown")
