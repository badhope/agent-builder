"""Aggregated daily usage counters per user (rate limit / quota)."""

from __future__ import annotations

import uuid
from datetime import date

from app.db.session import Base
from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UsageCounter(Base):
    """Per-day usage counter for a user."""

    __tablename__ = "usage_counters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_uploaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_downloaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    webhook_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_usage_user_day"),
    )
