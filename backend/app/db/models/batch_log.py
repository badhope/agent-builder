"""Per-batch log records (lifecycle events for the parent batch)."""
from __future__ import annotations

import uuid
from datetime import datetime

from app.db.session import Base
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class BatchLog(Base):
    """Lifecycle events for a batch aggregate (created, started, completed, etc.)."""

    __tablename__ = "batch_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    level: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    event: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    batch: Mapped[Batch] = relationship(lazy="joined")  # noqa: F821

    __table_args__ = (Index("ix_batch_logs_event", "event"),)
