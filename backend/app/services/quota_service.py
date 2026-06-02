"""Per-user quota enforcement.

Checks are invoked:

* before a direct upload (size cap, daily-conversion cap, storage cap, concurrent-tasks)
* before a conversion enqueue
* before an API key creation
* before a webhook subscription creation

Violations raise :class:`RateLimitExceededError` with structured
``details`` so the API client can show actionable messages.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.task import Task, TaskState
from app.db.models.usage import UsageCounter
from app.db.models.user import User
from app.exceptions import RateLimitExceededError


def _today_utc() -> date:
    return datetime.now(tz=UTC).date()


async def _get_or_create_counter(
    session: AsyncSession, user_id: uuid.UUID, day: date,
) -> UsageCounter:
    stmt = select(UsageCounter).where(
        UsageCounter.user_id == user_id, UsageCounter.day == day,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row
    row = UsageCounter(user_id=user_id, day=day)
    session.add(row)
    await session.flush()
    return row


class QuotaService:
    """High-level quota checks / counter increments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- checks (raise on violation) ----

    async def check_can_upload(self, user: User, size_bytes: int) -> None:
        await self.check_file_size(user, size_bytes)
        await self.check_storage(user, size_bytes)

    async def check_file_size(self, user: User, size_bytes: int) -> None:
        limit = user.quota_max_file_size_mb * 1024 * 1024
        if size_bytes > limit:
            raise RateLimitExceededError(
                f"File size exceeds your plan limit ({user.quota_max_file_size_mb} MB).",
                code="QUOTA_FILE_SIZE",
                details={
                    "max_bytes": limit,
                    "max_mb": user.quota_max_file_size_mb,
                    "size_bytes": size_bytes,
                },
            )

    async def check_storage(self, user: User, additional_bytes: int) -> None:
        from app.services.storage_service import StorageService
        storage = StorageService()
        used = await storage.storage_used_for_user(self.session, user.id)
        cap = user.quota_storage_mb * 1024 * 1024
        if used + additional_bytes > cap:
            raise RateLimitExceededError(
                "Storage quota exceeded.",
                code="QUOTA_STORAGE",
                details={
                    "used_bytes": used,
                    "cap_bytes": cap,
                    "cap_mb": user.quota_storage_mb,
                    "additional_bytes": additional_bytes,
                },
            )

    async def check_can_convert(self, user: User) -> None:
        await self.check_daily_conversions(user)
        await self.check_concurrency(user)

    async def check_daily_conversions(self, user: User) -> None:
        today = _today_utc()
        counter = await _get_or_create_counter(self.session, user.id, today)
        if counter.conversions >= user.quota_conversions_per_day:
            raise RateLimitExceededError(
                "Daily conversion quota exceeded.",
                code="QUOTA_DAILY_CONVERSIONS",
                details={
                    "limit": user.quota_conversions_per_day,
                    "used": counter.conversions,
                    "day": today.isoformat(),
                },
            )

    async def check_concurrency(self, user: User) -> None:
        stmt = select(func.count()).select_from(Task).where(
            Task.owner_id == user.id,
            Task.state.in_(
                [TaskState.PENDING, TaskState.QUEUED, TaskState.RUNNING]
            ),
        )
        active = int((await self.session.execute(stmt)).scalar_one())
        if active >= user.quota_concurrent_tasks:
            raise RateLimitExceededError(
                "Maximum concurrent tasks reached.",
                code="QUOTA_CONCURRENCY",
                details={
                    "limit": user.quota_concurrent_tasks,
                    "active": active,
                },
            )

    # ---- counters (best-effort) ----

    async def increment_conversion(self, user: User) -> None:
        counter = await _get_or_create_counter(
            self.session, user.id, _today_utc(),
        )
        counter.conversions += 1

    async def increment_upload(self, user: User, bytes_count: int) -> None:
        counter = await _get_or_create_counter(
            self.session, user.id, _today_utc(),
        )
        counter.bytes_uploaded += int(bytes_count)

    async def increment_download(self, user: User, bytes_count: int) -> None:
        counter = await _get_or_create_counter(
            self.session, user.id, _today_utc(),
        )
        counter.bytes_downloaded += int(bytes_count)

    async def increment_api_call(self, user: User) -> None:
        counter = await _get_or_create_counter(
            self.session, user.id, _today_utc(),
        )
        counter.api_calls += 1

    async def increment_webhook_call(self, user: User) -> None:
        counter = await _get_or_create_counter(
            self.session, user.id, _today_utc(),
        )
        counter.webhook_calls += 1


__all__ = ["QuotaService"]
