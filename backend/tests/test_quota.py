"""Quota service unit tests.

Tests ``QuotaService`` against an in-memory database.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User, UserPlan
from app.services.quota_service import QuotaService, RateLimitExceededError


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _mk_user(session: AsyncSession, **kw) -> User:
    from app.services.user_service import UserService

    svc = UserService(session)
    return await svc.create(
        email=f"q+{uuid.uuid4().hex[:8]}@example.com",
        password="x" * 20,
        plan=kw.pop("plan", UserPlan.FREE),
        **kw,
    )


async def test_free_plan_storage_quota_enforced(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session, plan=UserPlan.FREE)
    qs = QuotaService(db_session)
    # FREE plan max upload size is 50 MB by default
    assert user.quota_max_file_size_mb == 50
    # Below the cap — should be allowed
    await qs.check_can_upload(user, size_bytes=10 * 1024 * 1024)
    # At the cap — should still be allowed
    await qs.check_can_upload(user, size_bytes=49 * 1024 * 1024)
    # Over the cap — should raise
    with pytest.raises(RateLimitExceededError):
        await qs.check_can_upload(user, size_bytes=51 * 1024 * 1024)


async def test_pro_plan_daily_conversions(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session, plan=UserPlan.PRO)
    qs = QuotaService(db_session)
    # PRO plan = 1000 conversions/day, generous
    assert user.quota_conversions_per_day == 1000
    # First check should pass (counter starts at 0)
    await qs.check_daily_conversions(user)
    # Increment a few times — still well under
    for _ in range(5):
        await qs.increment_conversion(user)


async def test_enterprise_unlimited_daily(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session, plan=UserPlan.ENTERPRISE)
    qs = QuotaService(db_session)
    # Enterprise quota is huge — should never trip
    await qs.check_daily_conversions(user)


async def test_concurrency_check(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session, plan=UserPlan.FREE)
    qs = QuotaService(db_session)
    # FREE plan default concurrency is low
    assert user.quota_concurrent_tasks >= 1
    # Should not raise
    await qs.check_concurrency(user)


async def test_increment_upload(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session, plan=UserPlan.ENTERPRISE)
    qs = QuotaService(db_session)
    # Should not raise
    await qs.increment_upload(user, bytes_count=1024)
    await qs.increment_upload(user, bytes_count=2048)


async def test_check_file_size(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session, plan=UserPlan.FREE)
    qs = QuotaService(db_session)
    # Below the limit
    await qs.check_file_size(user, size_bytes=1024 * 1024)  # 1 MB
    # Over the limit (50 MB cap)
    with pytest.raises(RateLimitExceededError):
        await qs.check_file_size(user, size_bytes=60 * 1024 * 1024)
