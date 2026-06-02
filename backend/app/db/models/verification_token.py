"""Email verification & password reset tokens, 2FA backup codes, etc.

The model is a single polymorphic table — ``purpose`` distinguishes
verification, password reset, api-key confirmation, and 2FA challenges.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from app.db.session import Base
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class TokenPurpose(StrEnum):
    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"
    APIKEY_CONFIRM = "apikey_confirm"
    TOTP_CHALLENGE = "totp_challenge"
    ACCOUNT_DELETE = "account_delete"


class VerificationToken(Base):
    """Single-use token (random URL-safe) tied to a user and a purpose."""

    __tablename__ = "verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    purpose: Mapped[TokenPurpose] = mapped_column(String(40), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # The first 12 chars of the plaintext (UX)
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False)

    # Optional context payload (email being verified, IP, etc.)
    context: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False,
    )

    created_ip: Mapped[str | None] = mapped_column(INET)
    created_user_agent: Mapped[str | None] = mapped_column(String(500))

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_vt_user_purpose_active", "user_id", "purpose"),
    )
