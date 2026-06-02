"""Webhook subscription + delivery service.

The service speaks two new models:

* :class:`WebhookSubscription` — a persistent per-user URL + events list
  + optional signing secret.
* :class:`WebhookDelivery` — a single delivery attempt (with retries).

Calls go through :func:`enqueue_event`, which fans the event out to
every matching subscription, creates a delivery row, and lets the
background worker (:mod:`app.workers.webhook`) drive the actual HTTP
call.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import sign_webhook_payload
from app.db.models.user import User
from app.db.models.webhook import (
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEvent,
    WebhookSubscription,
)
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger
from app.settings import get_settings

logger = get_logger(__name__)


def _event_matches(subscription: WebhookSubscription, event: str) -> bool:
    if not subscription.events:
        return True  # empty list = subscribe to all
    return event in subscription.events


def _filter_matches(subscription: WebhookSubscription, payload: dict[str, Any]) -> bool:
    flt = subscription.filter or {}
    for key, expected in flt.items():
        actual = payload.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


class WebhookService:
    """Webhook subscription CRUD + delivery queue management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---- subscriptions ----

    async def list_subscriptions(
        self, user_id: uuid.UUID | str, *, limit: int = 50, offset: int = 0,
    ) -> tuple[list[WebhookSubscription], int]:
        uid = self._coerce(user_id)
        stmt = (
            select(WebhookSubscription)
            .where(WebhookSubscription.user_id == uid)
            .order_by(desc(WebhookSubscription.created_at))
            .limit(limit)
            .offset(offset)
        )
        count = select(func.count()).select_from(WebhookSubscription).where(
            WebhookSubscription.user_id == uid,
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count)).scalar_one())
        return rows, total

    async def get_subscription(
        self, user_id: uuid.UUID | str, subscription_id: uuid.UUID | str,
    ) -> WebhookSubscription:
        sub = await self._get_sub_for_user(user_id, subscription_id)
        return sub

    async def create_subscription(
        self,
        user_id: uuid.UUID | str,
        *,
        url: str,
        events: list[str] | None = None,
        description: str | None = None,
        secret: str | None = None,
        is_active: bool = True,
        filter: dict[str, Any] | None = None,
    ) -> WebhookSubscription:
        # Validate events
        valid_events = {e.value for e in WebhookEvent}
        for e in events or []:
            if e not in valid_events:
                raise ValidationError(
                    f"Unknown event type: {e}",
                    code="INVALID_WEBHOOK_EVENT",
                    details={"valid": sorted(valid_events)},
                )
        # SECURITY: reject URLs that would target internal network ranges
        # (loopback, RFC1918, link-local, cloud metadata, etc.). The check is
        # repeated in ``attempt`` because DNS can rebind between write and
        # delivery, but rejecting at create-time gives the user a clear
        # error and avoids persisting a dangerous URL.
        from app.core.ssrf import is_safe_webhook_url
        safe, reason = is_safe_webhook_url(url)
        if not safe:
            raise ValidationError(
                f"Webhook URL rejected: {reason}",
                code="UNSAFE_WEBHOOK_URL",
                details={"reason": reason},
            )
        sub = WebhookSubscription(
            id=uuid.uuid4(),
            user_id=self._coerce(user_id),
            url=url,
            description=description,
            events=events or [],
            secret=secret,
            filter=filter or {},
            is_active=is_active,
        )
        self.db.add(sub)
        await self.db.flush()
        return sub

    async def update_subscription(
        self,
        user_id: uuid.UUID | str,
        subscription_id: uuid.UUID | str,
        *,
        url: str | None = None,
        events: list[str] | None = None,
        description: str | None = None,
        secret: str | None = None,
        is_active: bool | None = None,
        filter: dict[str, Any] | None = None,
    ) -> WebhookSubscription:
        sub = await self._get_sub_for_user(user_id, subscription_id)
        if url is not None:
            sub.url = url
        if events is not None:
            sub.events = events
        if description is not None:
            sub.description = description
        if secret is not None:
            sub.secret = secret
        if is_active is not None:
            sub.is_active = is_active
        if filter is not None:
            sub.filter = filter
        await self.db.flush()
        return sub

    async def delete_subscription(
        self, user_id: uuid.UUID | str, subscription_id: uuid.UUID | str,
    ) -> None:
        sub = await self._get_sub_for_user(user_id, subscription_id)
        await self.db.delete(sub)
        await self.db.flush()

    # ---- delivery queue ----

    async def enqueue_event(
        self,
        user: User,
        event: str | WebhookEvent,
        payload: dict[str, Any],
    ) -> list[WebhookDelivery]:
        """Fan an event out to every active subscription that matches.

        Returns the list of created delivery rows.
        """
        if isinstance(event, WebhookEvent):
            event = event.value
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.user_id == user.id,
            WebhookSubscription.is_active.is_(True),
        )
        subs = list((await self.db.execute(stmt)).scalars().all())
        created: list[WebhookDelivery] = []
        for sub in subs:
            if not _event_matches(sub, event):
                continue
            if not _filter_matches(sub, payload):
                continue
            secret = sub.secret or user.webhook_secret or ""
            delivery = WebhookDelivery(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                user_id=user.id,
                event_type=event,
                payload=payload,
                url=sub.url,
                secret_used=secret,
                status=WebhookDeliveryStatus.PENDING,
                next_attempt_at=datetime.now(tz=UTC),
            )
            self.db.add(delivery)
            created.append(delivery)
        await self.db.flush()
        if created:
            logger.info(
                "webhook.enqueue_event",
                event=event, user_id=str(user.id), deliveries=len(created),
            )
        return created

    async def enqueue_direct(
        self,
        user: User,
        *,
        url: str,
        event: str,
        payload: dict[str, Any],
        secret: str | None = None,
    ) -> WebhookDelivery:
        """Enqueue a one-off delivery (used for per-task webhook overrides)."""
        secret = secret or user.webhook_secret or ""
        delivery = WebhookDelivery(
            id=uuid.uuid4(),
            subscription_id=uuid.uuid4(),  # synthetic; no subscription row
            user_id=user.id,
            event_type=event,
            payload=payload,
            url=url,
            secret_used=secret,
            status=WebhookDeliveryStatus.PENDING,
            next_attempt_at=datetime.now(tz=UTC),
        )
        self.db.add(delivery)
        await self.db.flush()
        return delivery

    async def pending(self, limit: int = 50) -> list[WebhookDelivery]:
        now = datetime.now(tz=UTC)
        stmt = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == WebhookDeliveryStatus.PENDING,
                WebhookDelivery.next_attempt_at <= now,
            )
            .order_by(WebhookDelivery.next_attempt_at)
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def attempt(
        self, delivery: WebhookDelivery, *, secret: str | None = None,
    ) -> bool:
        """Try a single delivery; updates the row in place. Returns True on 2xx."""
        settings = get_settings()
        use_secret = secret or delivery.secret_used
        body = json.dumps(delivery.payload, default=str).encode("utf-8")
        sig = sign_webhook_payload(body, use_secret) if use_secret else ""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DocFormatConverter-Webhook/1.0",
            "X-Webhook-Event": delivery.event_type,
            "X-Webhook-Delivery": str(delivery.id),
        }
        if sig:
            headers["X-Webhook-Signature"] = sig

        # SECURITY: SSRF defense — refuse to deliver to private/loopback/metadata IPs.
        from app.core.ssrf import is_safe_webhook_url
        safe, reason = is_safe_webhook_url(delivery.url)
        if not safe:
            delivery.attempts += 1
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.last_error = f"SSRF_BLOCKED:{reason}"
            delivery.next_attempt_at = None
            logger.warning(
                "webhook.ssrf_blocked",
                delivery_id=str(delivery.id),
                url=delivery.url,
                reason=reason,
            )
            return False

        delivery.attempts += 1
        try:
            # SECURITY: never follow redirects — a 302 to a private IP would
            # otherwise be a viable SSRF vector.
            async with httpx.AsyncClient(
                timeout=settings.webhook.timeout_s,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    delivery.url, content=body, headers=headers,
                )
        except Exception as exc:
            delivery.last_error = str(exc)[:500]
            self._schedule_retry(delivery)
            return False

        delivery.response_status = response.status_code
        delivery.duration_ms = int(response.elapsed.total_seconds() * 1000) if response.elapsed else None
        delivery.response_body = (response.text or "")[:4096]
        if 200 <= response.status_code < 300:
            delivery.status = WebhookDeliveryStatus.DELIVERED
            delivery.delivered_at = datetime.now(tz=UTC)
            # Update subscription stats
            await self._update_sub_stats(
                delivery, delivered=True, status_code=response.status_code,
            )
            return True
        delivery.last_error = f"HTTP {response.status_code}"
        self._schedule_retry(delivery)
        await self._update_sub_stats(
            delivery, delivered=False, status_code=response.status_code,
        )
        return False

    def _schedule_retry(self, delivery: WebhookDelivery) -> None:
        if delivery.attempts >= delivery.max_attempts:
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.next_attempt_at = None
            return
        backoff = get_settings().webhook.backoff_base_s ** delivery.attempts
        delivery.next_attempt_at = datetime.now(tz=UTC) + timedelta(
            seconds=backoff,
        )

    async def _update_sub_stats(
        self, delivery: WebhookDelivery, *, delivered: bool, status_code: int | None,
    ) -> None:
        # The synthetic row (no subscription) has a random uuid; skip if missing
        sub = await self.db.get(WebhookSubscription, delivery.subscription_id)
        if sub is None:
            return
        sub.last_triggered_at = datetime.now(tz=UTC)
        sub.last_status = status_code
        if delivered:
            sub.total_delivered += 1
        else:
            sub.total_failed += 1
            sub.last_error = delivery.last_error

    async def test(
        self,
        user: User,
        subscription_id: uuid.UUID | str,
    ) -> dict[str, Any]:
        """Send a synthetic ``webhook.test`` event to the subscription."""
        sub = await self._get_sub_for_user(user.id, subscription_id)
        secret = sub.secret or user.webhook_secret or ""
        payload = {
            "event": "webhook.test",
            "subscription_id": str(sub.id),
            "ts": datetime.now(tz=UTC).isoformat(),
        }
        body = json.dumps(payload, default=str).encode("utf-8")
        sig = sign_webhook_payload(body, secret) if secret else ""
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": "webhook.test",
            "X-Webhook-Signature": sig,
        }
        started = datetime.now(tz=UTC)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(sub.url, content=body, headers=headers)
            elapsed = (datetime.now(tz=UTC) - started).total_seconds() * 1000
            return {
                "status": "delivered" if 200 <= r.status_code < 300 else "failed",
                "response_status": r.status_code,
                "duration_ms": int(elapsed),
                "error": None if 200 <= r.status_code < 300 else f"HTTP {r.status_code}",
            }
        except Exception as exc:
            return {
                "status": "failed",
                "response_status": None,
                "duration_ms": None,
                "error": str(exc),
            }

    # ---- internal ----

    async def _get_sub_for_user(
        self, user_id: uuid.UUID | str, subscription_id: uuid.UUID | str,
    ) -> WebhookSubscription:
        try:
            sid = subscription_id if isinstance(subscription_id, uuid.UUID) else uuid.UUID(str(subscription_id))
        except (ValueError, TypeError) as exc:
            raise NotFoundError("Webhook subscription not found.", code="WEBHOOK_NOT_FOUND") from exc
        sub = await self.db.get(WebhookSubscription, sid)
        if sub is None or sub.user_id != self._coerce(user_id):
            raise NotFoundError("Webhook subscription not found.", code="WEBHOOK_NOT_FOUND")
        return sub

    @staticmethod
    def _coerce(user_id: uuid.UUID | str) -> uuid.UUID:
        if isinstance(user_id, uuid.UUID):
            return user_id
        return uuid.UUID(str(user_id))


__all__ = ["WebhookService"]
