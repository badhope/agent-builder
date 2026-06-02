"""Webhook subscription + delivery models.

Two tables:
* ``webhook_subscriptions`` — per-user subscriptions (URL + events + secret).
* ``webhook_deliveries``  — every delivery attempt (with retries).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from app.db.session import Base
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class WebhookEvent(StrEnum):
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    BATCH_CREATED = "batch.created"
    BATCH_COMPLETED = "batch.completed"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_APIKEY_CREATED = "user.apikey_created"


class WebhookSubscription(Base):
    """A user's persistent subscription to one or more event types."""

    __tablename__ = "webhook_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))

    # Events: list of WebhookEvent values; empty = "all"
    events: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Per-subscription signing secret; if NULL, falls back to user.webhook_secret
    secret: Mapped[str | None] = mapped_column(String(64))

    # Filter — JSON object forwarded in delivery for routing
    filter: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Delivery statistics
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    total_delivered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="webhooks", lazy="joined")  # noqa: F821
    deliveries: Mapped[list[WebhookDelivery]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_webhook_sub_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WebhookSubscription {self.id} {self.url[:40]}>"


class WebhookDeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WebhookDelivery(Base):
    """A single delivery attempt (with retries) for a webhook payload."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret_used: Mapped[str] = mapped_column(String(64), nullable=False)

    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    response_headers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    remote_ip: Mapped[str | None] = mapped_column(INET)

    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        String(20), default=WebhookDeliveryStatus.PENDING, nullable=False, index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)

    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subscription: Mapped[WebhookSubscription] = relationship(back_populates="deliveries")

    __table_args__ = (
        Index("ix_webhook_delivery_pending", "next_attempt_at",
              postgresql_where=(status == WebhookDeliveryStatus.PENDING)),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WebhookDelivery {self.id} {self.status}>"


__all__ = [
    "WebhookDelivery",
    "WebhookDeliveryStatus",
    "WebhookEvent",
    "WebhookSubscription",
]
