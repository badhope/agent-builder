"""Webhook subscription CRUD + delivery tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.webhook_service import WebhookService


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _mk_user(db_session: AsyncSession) -> User:
    from app.services.user_service import UserService
    from app.db.models.user import UserPlan

    svc = UserService(db_session)
    return await svc.create(
        email=f"wh+{uuid.uuid4().hex[:8]}@example.com",
        password="x" * 20,
        plan=UserPlan.ENTERPRISE,
    )


async def test_create_subscription(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session)
    svc = WebhookService(db_session)
    sub = await svc.create_subscription(
        owner_id=user.id,
        url="https://example.com/hook",
        events=["task.created", "task.completed"],
        secret="s3cr3t",
        description="test",
    )
    assert sub.id is not None
    assert sub.events == ["task.created", "task.completed"]
    assert sub.secret_hash  # hashed, not stored in plaintext
    assert sub.secret_hint  # short hint


async def test_list_subscriptions(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session)
    svc = WebhookService(db_session)
    await svc.create_subscription(
        owner_id=user.id, url="https://e.com/a", events=["task.created"],
    )
    await svc.create_subscription(
        owner_id=user.id, url="https://e.com/b", events=["task.completed"],
    )
    subs, total = await svc.list_subscriptions(owner_id=user.id)
    assert total == 2
    assert {s.url for s in subs} == {"https://e.com/a", "https://e.com/b"}


async def test_update_subscription(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session)
    svc = WebhookService(db_session)
    sub = await svc.create_subscription(
        owner_id=user.id, url="https://e.com/a", events=["task.created"],
    )
    updated = await svc.update_subscription(
        owner_id=user.id, subscription_id=sub.id,
        url="https://e.com/b", is_active=False,
    )
    assert updated.url == "https://e.com/b"
    assert updated.is_active is False


async def test_delete_subscription_soft(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session)
    svc = WebhookService(db_session)
    sub = await svc.create_subscription(
        owner_id=user.id, url="https://e.com/a", events=["task.created"],
    )
    await svc.delete_subscription(owner_id=user.id, subscription_id=sub.id)
    subs, total = await svc.list_subscriptions(owner_id=user.id, include_deleted=False)
    assert total == 0


async def test_enqueue_event_fanout(db_session: AsyncSession) -> None:
    from app.db.models.webhook import WebhookEvent

    user = await _mk_user(db_session)
    svc = WebhookService(db_session)
    await svc.create_subscription(
        owner_id=user.id, url="https://a.com/hook", events=[WebhookEvent.TASK_CREATED],
    )
    await svc.create_subscription(
        owner_id=user.id, url="https://b.com/hook", events=[WebhookEvent.TASK_CREATED],
    )
    created = await svc.enqueue_event(
        owner_id=user.id,
        event=WebhookEvent.TASK_CREATED,
        payload={"task_id": "abc123"},
    )
    assert len(created) == 2
    assert all(d.event == WebhookEvent.TASK_CREATED for d in created)
