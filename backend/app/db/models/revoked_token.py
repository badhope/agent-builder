"""Persisted record of revoked refresh-token JTIs.

When a user logs out, or their password is changed, or an admin revokes a
session, the refresh-token JTI is recorded here. ``AuthService.refresh``
rejects any token whose JTI is present, making the revocation effective
immediately (CWE-613 insufficient session invalidation).

Old rows are periodically pruned by the cleanup worker based on
``expires_at`` (the natural token expiry).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RevokedToken(Base):
    """A JWT JTI that has been explicitly revoked before its natural expiry."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(60), nullable=False, default="logout")
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )

    __table_args__ = (
        Index("ix_revoked_tokens_user_revoked", "user_id", "revoked_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RevokedToken jti={self.jti[:8]}… reason={self.reason}>"


__all__ = ["RevokedToken"]
