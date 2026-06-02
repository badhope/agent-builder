"""Periodic maintenance jobs (queue depth, storage quota, orphan detection)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.db.models.file import File
from app.db.models.task import Task
from app.db.models.user import User
from app.db.session import get_sessionmaker
from app.logging_config import get_logger
from app.observability.metrics import QUEUE_DEPTH
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.maintenance.recompute_storage_quotas")
def recompute_storage_quotas() -> dict:
    return asyncio.run(_recompute_storage_quotas())


async def _recompute_storage_quotas() -> dict:
    """Re-derive ``User.quota_storage_mb`` baselines from current usage.

    This is a metrics-and-alerting job, not a quota enforcement job:
    the byte totals are logged so an external system can alert users
    who are at or above their storage limit.
    """
    sm = get_sessionmaker()
    now = datetime.now(tz=UTC)
    at_limit = 0
    over_limit = 0
    async with sm() as session:
        rows = (
            await session.execute(
                select(
                    User.id,
                    User.quota_storage_mb,
                    func.coalesce(func.sum(File.size), 0).label("used"),
                )
                .outerjoin(
                    File,
                    (File.owner_id == User.id) & (File.deleted_at.is_(None)),
                )
                .where(User.deleted_at.is_(None))
                .group_by(User.id, User.quota_storage_mb)
            )
        ).all()
        for uid, quota_mb, used in rows:
            cap_bytes = int(quota_mb) * 1024 * 1024
            if cap_bytes and int(used) >= cap_bytes:
                over_limit += 1
            elif cap_bytes and int(used) >= cap_bytes * 0.9:
                at_limit += 1
    if at_limit or over_limit:
        logger.info(
            "maintenance.storage_warnings",
            at_limit=at_limit, over_limit=over_limit,
        )
    return {"at_limit": at_limit, "over_limit": over_limit, "checked_at": now.isoformat()}


@celery_app.task(name="app.workers.maintenance.detect_orphan_files")
def detect_orphan_files() -> dict:
    return asyncio.run(_detect_orphan_files())


async def _detect_orphan_files() -> dict:
    """Find File rows that exist but have no associated task or user."""
    sm = get_sessionmaker()
    async with sm() as session:
        # Files with no owner (should never happen) and no task
        rows = (
            await session.execute(
                select(func.count())
                .select_from(File)
                .where(
                    File.task_id.is_(None),
                    File.batch_id.is_(None),
                    File.purpose != "avatar",
                    File.deleted_at.is_(None),
                )
            )
        ).scalar_one()
    if rows:
        logger.info("maintenance.orphan_files", count=int(rows))
    return {"orphan": int(rows)}


@celery_app.task(name="app.workers.maintenance.refresh_queue_depth")
def refresh_queue_depth() -> dict:
    return asyncio.run(_refresh_queue_depth())


async def _refresh_queue_depth() -> dict:
    sm = get_sessionmaker()
    depth: dict[str, int] = {}
    async with sm() as session:
        rows = (
            await session.execute(
                select(Task.state, func.count()).group_by(Task.state)
            )
        ).all()
        for state_value, count in rows:
            depth[state_value.value] = int(count)
    for q, d in depth.items():
        QUEUE_DEPTH.labels(queue=q).set(d)
    return {"depth": depth}


__all__ = [
    "detect_orphan_files",
    "recompute_storage_quotas",
    "refresh_queue_depth",
]
