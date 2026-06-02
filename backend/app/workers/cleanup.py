"""Maintenance workers: expiry, purging, queue bookkeeping."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update

from app.db.models.file import File
from app.db.models.idempotency import IdempotencyRecord
from app.db.models.revoked_token import RevokedToken
from app.db.models.task import Task, TaskState
from app.db.session import get_sessionmaker
from app.logging_config import get_logger
from app.observability.metrics import QUEUE_DEPTH
from app.services.storage_service import StorageService
from app.services.task_service import TaskService
from app.settings import get_settings
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.cleanup.expire_old_tasks")
def expire_old_tasks() -> dict:
    return asyncio.run(_expire_old_tasks())


async def _expire_old_tasks() -> dict:
    sm = get_sessionmaker()
    async with sm() as session:
        svc = TaskService(session)
        n = await svc.expire_old()
        await session.commit()
    if n:
        logger.info("cleanup.expired_tasks", count=n)
    return {"expired": n}


@celery_app.task(name="app.workers.cleanup.purge_expired_files")
def purge_expired_files() -> dict:
    return asyncio.run(_purge_expired_files())


async def _purge_expired_files() -> dict:
    sm = get_sessionmaker()
    settings = get_settings()
    now = datetime.now(tz=UTC)
    grace_cutoff = now - timedelta(days=settings.retention.soft_delete_grace_days)
    hard_delete_limit = settings.retention.hard_delete_batch_size
    soft_deleted = 0
    async with sm() as session:
        result = await session.execute(
            update(File)
            .where(
                File.expires_at < now,
                File.deleted_at.is_(None),
            )
            .values(deleted_at=now, deleted_reason="retention_elapsed")
        )
        await session.commit()
        soft_deleted = int(result.rowcount or 0)

    # Hard delete only files that have been soft-deleted past the grace period.
    # Previously this deleted ALL rows with deleted_at IS NOT NULL, which wiped
    # user-requested soft deletes that should still be restorable.
    keys: list[str] = []
    async with sm() as session:
        rows = (
            await session.execute(
                delete(File)
                .where(
                    File.deleted_at.is_not(None),
                    File.deleted_at < grace_cutoff,
                )
                .returning(File.storage_key)
                .limit(hard_delete_limit)
            )
        ).scalars().all()
        keys = [r for r in rows if r]
    hard_deleted = 0
    if keys:
        storage = StorageService()
        hard_deleted = await storage.delete_many(keys)
    if soft_deleted or hard_deleted:
        logger.info(
            "cleanup.purged_files",
            soft_deleted=soft_deleted, hard_deleted=hard_deleted,
        )
    return {"soft_deleted": soft_deleted, "hard_deleted": hard_deleted}


@celery_app.task(name="app.workers.cleanup.purge_idempotency_records")
def purge_idempotency_records() -> dict:
    return asyncio.run(_purge_idempotency_records())


async def _purge_idempotency_records() -> dict:
    sm = get_sessionmaker()
    now = datetime.now(tz=UTC)
    async with sm() as session:
        result = await session.execute(
            delete(IdempotencyRecord)
            .where(IdempotencyRecord.expires_at < now)
        )
        await session.commit()
        n = int(result.rowcount or 0)
    if n:
        logger.info("cleanup.purged_idempotency", count=n)
    return {"purged": n}


@celery_app.task(name="app.workers.cleanup.requeue_stuck_tasks")
def requeue_stuck_tasks() -> dict:
    """Re-queue tasks that have been in 'running' state for too long."""
    return asyncio.run(_requeue_stuck_tasks())


async def _requeue_stuck_tasks() -> dict:
    sm = get_sessionmaker()
    cutoff = datetime.now(tz=UTC)
    # Anything running for >30 min with no progress → mark failed
    from datetime import timedelta
    threshold = cutoff - timedelta(minutes=30)
    n = 0
    async with sm() as session:
        result = await session.execute(
            update(Task)
            .where(
                Task.state == TaskState.RUNNING,
                Task.started_at < threshold,
            )
            .values(
                state=TaskState.FAILED,
                error_code="TASK_STUCK",
                error_message="Task exceeded wall-clock limit; reaping",
                finished_at=cutoff,
            )
        )
        n = int(result.rowcount or 0)
        await session.commit()
    if n:
        logger.warning("cleanup.reaped_stuck_tasks", count=n)
    return {"reaped": n}


async def _purge_revoked_tokens() -> dict:
    """Delete expired RevokedToken rows (relying on natural JWT expiry)."""
    sm = get_sessionmaker()
    now = datetime.now(tz=UTC)
    async with sm() as session:
        result = await session.execute(
            delete(RevokedToken).where(RevokedToken.expires_at < now)
        )
        n = int(result.rowcount or 0)
        await session.commit()
    if n:
        logger.info("cleanup.purged_revoked_tokens", count=n)
    return {"purged": n}


@celery_app.task(name="app.workers.cleanup.refresh_metrics")
def refresh_metrics() -> dict:
    """Update the queue_depth gauge from Celery inspector."""
    return asyncio.run(_refresh_metrics())


async def _refresh_metrics() -> dict:
    try:
        from app.workers.celery_app import celery_app as app
        inspect = app.control.inspect(timeout=1.0)
        # active queues
        active_queues = inspect.active_queues() or {}
        depth: dict[str, int] = {}
        for worker, queues in active_queues.items():
            for q in queues:
                name = q.get("name", "default")
                depth[name] = depth.get(name, 0) + 1
        for q, d in depth.items():
            QUEUE_DEPTH.labels(queue=q).set(d)
        return {"depth": depth}
    except Exception as exc:
        logger.debug("metrics.refresh_failed", error=str(exc))
        return {"depth": {}}


__all__ = [
    "expire_old_tasks",
    "purge_expired_files",
    "purge_idempotency_records",
    "refresh_metrics",
    "requeue_stuck_tasks",
]
