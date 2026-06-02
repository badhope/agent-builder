"""Idempotency-key cache.

Each row records the response that was returned for a given (user, key)
pair so that a retry returns the same result.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.db.session import Base
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class IdempotencyRecord(Base):
    """A cached response for a (user, method, path, key) tuple."""

    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)

    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    response_headers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    in_flight: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "method", "path", "key", name="uq_idem_user_path_key"),
    )
