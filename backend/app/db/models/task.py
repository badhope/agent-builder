"""Task, Batch, and BatchItem models for tracking conversions.

A ``Task`` represents a single conversion (source → target) belonging to
a user. Each task can optionally belong to a ``Batch`` (a group of tasks
submitted together for convenience).

State machine:

    pending → queued → running → succeeded
                       │         └→ failed
                       └→ cancelled
    any terminal → expired (after the retention window)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from app.db.session import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class TaskState(StrEnum):
    """Lifecycle states of a single conversion task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Task(Base):
    """A single document conversion task."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
        index=True,
    )
    batch_index: Mapped[int | None] = mapped_column(Integer)

    # Source
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    source_format: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)

    # Target
    target_format: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    options_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # State
    state: Mapped[TaskState] = mapped_column(
        String(20), default=TaskState.PENDING, nullable=False, index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        String(20), default=TaskPriority.NORMAL, nullable=False,
    )
    backend: Mapped[str | None] = mapped_column(String(60))

    # Result
    output_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"),
    )
    output_format: Mapped[str | None] = mapped_column(String(20))
    output_size: Mapped[int | None] = mapped_column(Integer)
    output_sha256: Mapped[str | None] = mapped_column(String(64))

    # Error
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Progress
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_message: Mapped[str | None] = mapped_column(String(255))

    # Retry handling
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Webhook (per-task override; users may also have a global subscription)
    webhook_url: Mapped[str | None] = mapped_column(Text)
    webhook_secret: Mapped[str | None] = mapped_column(String(64))  # override per-task
    webhook_delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    webhook_last_error: Mapped[str | None] = mapped_column(Text)

    # Timekeeping
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    queue_time_ms: Mapped[int | None] = mapped_column(Integer)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)

    # Idempotency
    idempotency_key: Mapped[str | None] = mapped_column(String(120), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped[User] = relationship(back_populates="tasks", lazy="joined")  # noqa: F821
    source_file: Mapped[File] = relationship(  # noqa: F821
        back_populates="task", foreign_keys=[source_file_id], lazy="joined"
    )
    output_file: Mapped[File | None] = relationship(  # noqa: F821
        foreign_keys=[output_file_id], lazy="joined"
    )
    batch: Mapped[Batch | None] = relationship(back_populates="tasks")
    files: Mapped[list[File]] = relationship(  # noqa: F821
        back_populates="task", foreign_keys="File.task_id", cascade="all, delete-orphan"
    )
    logs: Mapped[list[TaskLog]] = relationship(  # noqa: F821
        back_populates="task", cascade="all, delete-orphan", order_by="TaskLog.created_at"
    )

    __table_args__ = (
        CheckConstraint("progress_pct BETWEEN 0 AND 100", name="ck_tasks_progress_range"),
        CheckConstraint("attempts >= 0", name="ck_tasks_attempts_nonneg"),
        Index("ix_tasks_owner_state", "owner_id", "state"),
        Index("ix_tasks_state_created", "state", "created_at"),
        Index("ix_tasks_state_priority", "state", "priority", "created_at"),
    )

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED, TaskState.EXPIRED,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task {self.id} {self.state} {self.source_format}→{self.target_format}>"


class Batch(Base):
    """A grouped set of conversion tasks submitted together."""

    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    state: Mapped[TaskState] = mapped_column(
        String(20), default=TaskState.PENDING, nullable=False, index=True,
    )

    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    running: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # The result archive (a ZIP of all outputs) — populated when the batch
    # is finished and ``archive_format`` is set to ``"zip"``.
    archive_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"),
    )
    archive_format: Mapped[str] = mapped_column(String(20), default="zip", nullable=False)

    # Webhook
    webhook_url: Mapped[str | None] = mapped_column(Text)
    webhook_secret: Mapped[str | None] = mapped_column(String(64))
    webhook_delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timekeeping
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # Idempotency
    idempotency_key: Mapped[str | None] = mapped_column(String(120), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped[User] = relationship(back_populates="batches", lazy="joined")  # noqa: F821
    tasks: Mapped[list[Task]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="Task.batch_index"
    )
    archive_file: Mapped[File | None] = relationship(foreign_keys=[archive_file_id])  # noqa: F821

    __table_args__ = (
        Index("ix_batches_owner_state", "owner_id", "state"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Batch {self.id} {self.state} {self.succeeded}/{self.total}>"


__all__ = ["Batch", "Task", "TaskPriority", "TaskState"]
