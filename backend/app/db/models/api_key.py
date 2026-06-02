"""API Key model.

* ``key_hash`` = SHA-256 of the full plaintext (computed by ``core.security.hash_api_key``).
* ``key_prefix`` = first 12 characters of the plaintext, kept for UX.
* ``key_last4`` = last 4 characters of the plaintext.
* ``scopes`` = explicit list of scopes; if empty, defaults to the user's
  default scopes (read/write on own resources).
* ``expires_at`` = optional absolute expiry; the dep checker rejects expired keys.
"""

from __future__ import annotations

import uuid
from datetime import datetime

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


class ApiKey(Base):
    """A long-lived, scoped API key for a user."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_last4: Mapped[str] = mapped_column(String(8), nullable=False)

    name: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_ip: Mapped[str | None] = mapped_column(INET)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(255))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="api_keys", lazy="joined")  # noqa: F821

    __table_args__ = (
        Index("ix_api_keys_user_active", "user_id", "is_active"),
        Index("ix_api_keys_active_expires", "is_active", "expires_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ApiKey {self.key_prefix}…{self.key_last4}>"
