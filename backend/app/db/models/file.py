"""Persisted file records.

A ``File`` row describes one stored object. Files can be:
* a user upload (``purpose='source'``) — used as the source of a conversion;
* a generated output (``purpose='output'``) — produced by a converter;
* a user asset (``purpose='asset'``) — e.g. an avatar or thumbnail.

Each file is owned by a user (``owner_id``) and has an optional
``task_id`` and ``batch_id`` linking it to the work that produced it.
``scan_status`` records the result of the optional ClamAV scan and
``metadata_json`` stores format-specific extracted metadata (image
dimensions, PDF page count, etc.).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from app.db.session import Base
from sqlalchemy import (
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


class FilePurpose(StrEnum):
    """Why this file was stored."""

    SOURCE = "source"
    OUTPUT = "output"
    ASSET = "asset"
    AVATAR = "avatar"
    THUMBNAIL = "thumbnail"


class FileScanStatus(StrEnum):
    """Anti-virus scan result."""

    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    SKIPPED = "skipped"


class File(Base):
    """A stored object (input upload, produced output, or asset)."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        index=True,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
        index=True,
    )

    # Storage location
    storage_backend: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    storage_bucket: Mapped[str | None] = mapped_column(String(120))
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    # Identity
    purpose: Mapped[FilePurpose] = mapped_column(
        String(20), default=FilePurpose.SOURCE, nullable=False, index=True,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    format: Mapped[str | None] = mapped_column(String(20), index=True)

    # Quality / safety
    scan_status: Mapped[FileScanStatus] = mapped_column(
        String(20), default=FileScanStatus.PENDING, nullable=False,
    )
    scan_signature: Mapped[str | None] = mapped_column(String(255))
    scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scan_engine: Mapped[str | None] = mapped_column(String(60))

    # Format-specific metadata (image dimensions, PDF page count, etc.)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Thumbnail (if generated)
    thumbnail_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"),
    )

    # Usage / access
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_download_ip: Mapped[str | None] = mapped_column(INET)

    # Lifecycle
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_reason: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped[User] = relationship(back_populates="files", lazy="joined")  # noqa: F821
    task: Mapped[Task | None] = relationship(back_populates="files", foreign_keys=[task_id])  # noqa: F821
    thumbnail: Mapped[File | None] = relationship(remote_side="File.id")

    __table_args__ = (
        Index("ix_files_owner_purpose", "owner_id", "purpose"),
        Index("ix_files_owner_created", "owner_id", "created_at"),
        Index("ix_files_active", "expires_at", postgresql_where=(deleted_at.is_(None))),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<File {self.id} {self.filename} purpose={self.purpose}>"
