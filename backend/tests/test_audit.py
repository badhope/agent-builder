"""Audit log service tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _mk_user(db_session: AsyncSession):
    from app.services.user_service import UserService
    from app.db.models.user import UserPlan

    svc = UserService(db_session)
    return await svc.create(
        email=f"audit+{uuid.uuid4().hex[:8]}@example.com",
        password="x" * 20,
        plan=UserPlan.ENTERPRISE,
    )


async def test_record_and_list(db_session: AsyncSession) -> None:
    from app.services.audit_service import AuditService

    user = await _mk_user(db_session)
    svc = AuditService(db_session)
    await svc.record(
        actor_id=user.id,
        action="user.login",
        resource_type="user",
        resource_id=str(user.id),
        details={"ip": "127.0.0.1"},
    )
    await svc.record(
        actor_id=user.id,
        action="user.logout",
        resource_type="user",
        resource_id=str(user.id),
    )
    items, total = await svc.list(actor_id=user.id)
    assert total == 2
    actions = {it.action for it in items}
    assert actions == {"user.login", "user.logout"}


async def test_list_pagination(db_session: AsyncSession) -> None:
    from app.services.audit_service import AuditService

    user = await _mk_user(db_session)
    svc = AuditService(db_session)
    for i in range(5):
        await svc.record(
            actor_id=user.id, action=f"event.{i}",
            resource_type="x", resource_id=str(i),
        )
    page1, total = await svc.list(actor_id=user.id, limit=2, offset=0)
    page2, _ = await svc.list(actor_id=user.id, limit=2, offset=2)
    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    # No overlap
    assert {it.id for it in page1}.isdisjoint({it.id for it in page2})


async def test_filter_by_action(db_session: AsyncSession) -> None:
    from app.services.audit_service import AuditService

    user = await _mk_user(db_session)
    svc = AuditService(db_session)
    await svc.record(actor_id=user.id, action="a", resource_type="x", resource_id="1")
    await svc.record(actor_id=user.id, action="b", resource_type="x", resource_id="2")
    items, total = await svc.list(actor_id=user.id, action="a")
    assert total == 1
    assert items[0].action == "a"
