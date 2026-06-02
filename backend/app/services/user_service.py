"""User service — registration, lookup, profile updates, admin operations."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import password_manager
from app.db.models.user import User, UserPlan, UserRole
from app.exceptions import ConflictError, NotFoundError


class UserService:
    """CRUD + business logic for ``User``."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---- Lookups ----

    async def get_by_id(self, user_id: uuid.UUID | str | None) -> User | None:
        if user_id is None:
            return None
        try:
            uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            return None
        return await self.db.get(User, uid)

    async def get_by_email(self, email: str) -> User | None:
        if not email:
            return None
        stmt = select(User).where(
            or_(User.email == email.lower(), User.email_lower == email.lower()),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ---- Creation ----

    async def create(
        self,
        email: str,
        password: str,
        *,
        full_name: str | None = None,
        is_admin: bool = False,
        role: UserRole | str = UserRole.USER,
        plan: UserPlan | str = UserPlan.FREE,
    ) -> User:
        email_norm = email.lower()
        existing = await self.get_by_email(email_norm)
        if existing is not None:
            raise ConflictError(
                "A user with this email already exists.",
                code="USER_EXISTS",
            )

        # Role / plan coercion
        if isinstance(role, str):
            role = UserRole(role)
        if isinstance(plan, str):
            plan = UserPlan(plan)

        user = User(
            id=uuid.uuid4(),
            email=email_norm,
            email_lower=email_norm,
            full_name=full_name,
            password_hash=password_manager.hash(password),
            role=role,
            plan=plan,
            is_admin=is_admin,
            is_active=True,
            is_verified=False,
            webhook_secret=secrets.token_urlsafe(32),
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A user with this email already exists.",
                code="USER_EXISTS",
            ) from exc
        return user

    # ---- Touches ----

    async def touch_last_login(self, user: User, ip: str | None = None) -> None:
        await self.db.execute(
            update(User)
            .where(User.id == user.id)
            .values(
                last_login_at=datetime.now(tz=UTC),
                last_login_ip=ip,
            )
        )

    async def mark_verified(self, user: User) -> None:
        user.is_verified = True
        user.email_verified_at = datetime.now(tz=UTC)
        await self.db.flush()

    # ---- Self-service profile ----

    async def update_profile(
        self,
        user_id: uuid.UUID | str,
        *,
        full_name: str | None = None,
        avatar_url: str | None = None,
        preferences: dict | None = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        if full_name is not None:
            user.full_name = full_name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if preferences is not None:
            user.preferences = preferences
        await self.db.flush()
        return user

    async def change_password(self, user_id: uuid.UUID | str, new_password: str) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        user.password_hash = password_manager.hash(new_password)
        await self.db.flush()

    async def verify_password(self, user: User, password: str) -> bool:
        return password_manager.verify(password, user.password_hash)

    # ---- Activation ----

    async def deactivate(self, user_id: uuid.UUID | str) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        user.is_active = False
        await self.db.flush()

    async def set_active(self, user: User, active: bool) -> User:
        user.is_active = active
        await self.db.flush()
        return user

    # ---- Admin ----

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
        is_active: bool | None = None,
        role: UserRole | str | None = None,
    ) -> tuple[list[User], int]:
        stmt = select(User).order_by(desc(User.created_at))
        count_stmt = select(func.count()).select_from(User)
        if query:
            like = f"%{query.lower()}%"
            cond = or_(
                User.email_lower.like(like),
                User.full_name.ilike(like),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
            count_stmt = count_stmt.where(User.is_active.is_(is_active))
        if role is not None:
            if isinstance(role, str):
                role = UserRole(role)
            stmt = stmt.where(User.role == role)
            count_stmt = count_stmt.where(User.role == role)
        stmt = stmt.limit(limit).offset(offset)
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return rows, total

    async def admin_update(
        self,
        user_id: uuid.UUID | str,
        *,
        full_name: str | None = None,
        role: UserRole | str | None = None,
        plan: UserPlan | str | None = None,
        is_active: bool | None = None,
        is_verified: bool | None = None,
        quota_conversions_per_day: int | None = None,
        quota_storage_mb: int | None = None,
        quota_max_file_size_mb: int | None = None,
        quota_concurrent_tasks: int | None = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        if full_name is not None:
            user.full_name = full_name
        if role is not None:
            user.role = UserRole(role) if isinstance(role, str) else role
            user.is_admin = user.role == UserRole.ADMIN
        if plan is not None:
            user.plan = UserPlan(plan) if isinstance(plan, str) else plan
        if is_active is not None:
            user.is_active = is_active
        if is_verified is not None:
            user.is_verified = is_verified
            if is_verified and not user.email_verified_at:
                user.email_verified_at = datetime.now(tz=UTC)
        if quota_conversions_per_day is not None:
            user.quota_conversions_per_day = quota_conversions_per_day
        if quota_storage_mb is not None:
            user.quota_storage_mb = quota_storage_mb
        if quota_max_file_size_mb is not None:
            user.quota_max_file_size_mb = quota_max_file_size_mb
        if quota_concurrent_tasks is not None:
            user.quota_concurrent_tasks = quota_concurrent_tasks
        await self.db.flush()
        return user

    async def admin_delete(self, user_id: uuid.UUID | str) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        # Soft-delete: keep row for audit, mark inactive + deleted_at
        user.is_active = False
        user.deleted_at = datetime.now(tz=UTC)
        await self.db.flush()

    # ---- Stats ----

    async def count(self) -> int:
        stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        return int((await self.db.execute(stmt)).scalar_one())


__all__ = ["UserService"]
