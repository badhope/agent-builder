"""Per-task log records."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import IntEnum

from app.db.session import Base
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class TaskLog(Base):
    """A single log entry emitted by the worker for a given task."""

    __tablename__ = "task_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    level: Mapped[LogLevel] = mapped_column(default=LogLevel.INFO, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    worker_id: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    task: Mapped[Task] = relationship(back_populates="logs", lazy="joined")  # noqa: F821

    __table_args__ = (
        Index("ix_task_logs_errors", "level", postgresql_where=(level >= LogLevel.ERROR)),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TaskLog {self.task_id} {self.level.name}>"
