"""Webhook delivery worker — drain the delivery queue."""

from __future__ import annotations

import asyncio
import uuid

from app.db.models.webhook import WebhookDelivery, WebhookDeliveryStatus
from app.db.session import get_sessionmaker
from app.logging_config import get_logger
from app.services.webhook_service import WebhookService
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.webhook.deliver_pending")
def deliver_pending() -> dict:
    return asyncio.run(_deliver_pending())


async def _deliver_pending() -> dict:
    sm = get_sessionmaker()
    delivered = 0
    failed = 0
    async with sm() as session:
        svc = WebhookService(session)
        pending = await svc.pending(limit=200)
        for delivery in pending:
            ok = await svc.attempt(delivery)
            if ok:
                delivered += 1
            else:
                failed += 1
        await session.commit()
    if delivered or failed:
        logger.info(
            "webhook.batch", delivered=delivered, failed=failed,
        )
    return {"delivered": delivered, "failed": failed}


@celery_app.task(name="app.workers.webhook.deliver_one")
def deliver_one(delivery_id: str) -> dict:
    return asyncio.run(_deliver_one(delivery_id))


async def _deliver_one(delivery_id: str) -> dict:
    try:
        did = uuid.UUID(delivery_id)
    except ValueError:
        return {"status": "bad_id"}
    sm = get_sessionmaker()
    async with sm() as session:
        d = await session.get(WebhookDelivery, did)
        if d is None:
            return {"status": "missing"}
        if d.status != WebhookDeliveryStatus.PENDING:
            return {"status": "skipped", "state": d.status.value}
        ok = await WebhookService(session).attempt(d)
        await session.commit()
    return {"status": "delivered" if ok else "retry"}


__all__ = ["deliver_one", "deliver_pending"]
