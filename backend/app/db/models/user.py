"""User account model.

Single unified design used everywhere in the codebase:

* ``email`` is the unique identifier (case-insensitive uniqueness enforced
  in the Alembic migration via a lower-case index).
* ``full_name`` is the display name (was ``name`` in the earlier draft).
* ``role`` is the RBAC role; ``plan`` is the subscription tier. They are
  orthogonal — an admin can be on the free plan, a free user can be
  granted scoped API keys.
* ``is_active`` disables login without deleting the row.
* ``totp_enabled`` and ``totp_secret_enc`` enable TOTP 2FA.
* ``webhook_secret`` is the user's per-account secret used to sign
  outbound webhook payloads (HMAC-SHA256).
* Quotas are read by the quota enforcement middleware.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from app.db.session import Base
from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class UserPlan(StrEnum):
    """Subscription plan tier."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserRole(StrEnum):
    """RBAC role."""

    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class User(Base):
    """A registered user of the converter."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_lower: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )
    plan: Mapped[UserPlan] = mapped_column(
        SAEnum(UserPlan, name="user_plan"),
        default=UserPlan.FREE,
        nullable=False,
        index=True,
    )
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Quotas (overridable by plan or admin)
    quota_conversions_per_day: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    quota_storage_mb: Mapped[int] = mapped_column(Integer, default=1_000, nullable=False)
    quota_max_file_size_mb: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    quota_concurrent_tasks: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[str | None] = mapped_column(String(64))

    # 2FA
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text)  # encrypted with app key
    totp_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_codes_hash: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False,
    )  # hashed recovery codes

    # Per-user webhook signing secret (random 32 bytes, base64)
    webhook_secret: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # Preferences
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    api_keys: Mapped[list[ApiKey]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    files: Mapped[list[File]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )
    tasks: Mapped[list[Task]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
    batches: Mapped[list[Batch]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
    webhooks: Mapped[list[WebhookSubscription]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("email_lower", name="uq_users_email_lower"),
        Index("ix_users_active_verified", "is_active", "is_verified"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_moderator(self) -> bool:
        return self.role in {UserRole.MODERATOR, UserRole.ADMIN}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} role={self.role} plan={self.plan}>"
