"""API key service.

* ``list_for_user`` / ``create`` / ``revoke`` — owner-facing CRUD.
* ``verify_and_load`` — used by the auth dep to authenticate a request.
* ``update_last_used`` — touch ``use_count``/``last_used_at``/``last_used_ip``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    API_KEY_LIVE_PREFIX,
    API_KEY_TEST_PREFIX,
    generate_api_key,
    hash_api_key,
)
from app.db.models.api_key import ApiKey
from app.db.models.user import User
from app.exceptions import NotFoundError


class ApiKeyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID | str,
    ) -> list[ApiKey]:
        uid = self._coerce(user_id)
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == uid)
            .order_by(desc(ApiKey.created_at))
        )
        return list((await session.execute(stmt)).scalars().all())

    async def create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID | str,
        *,
        name: str,
        description: str | None = None,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        test_mode: bool = False,
    ) -> tuple[ApiKey, str]:
        uid = self._coerce(user_id)
        gen = generate_api_key(test_mode=test_mode)
        row = ApiKey(
            id=uuid.uuid4(),
            user_id=uid,
            key_hash=gen.hash,
            key_prefix=gen.prefix,
            key_last4=gen.last4,
            name=name,
            description=description,
            scopes=scopes or ["read", "write"],
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
        return row, gen.plaintext

    async def revoke(
        self,
        session: AsyncSession,
        user_id: uuid.UUID | str,
        key_id: str,
        reason: str | None = None,
    ) -> None:
        uid = self._coerce(user_id)
        try:
            kid = uuid.UUID(key_id)
        except ValueError as exc:
            raise NotFoundError("Invalid API key id.", code="API_KEY_NOT_FOUND") from exc
        row = (
            await session.execute(
                select(ApiKey).where(
                    ApiKey.id == kid, ApiKey.user_id == uid,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("API key not found.", code="API_KEY_NOT_FOUND")
        row.is_active = False
        row.revoked_at = datetime.now(tz=UTC)
        row.revoked_reason = reason
        await session.flush()

    async def verify_and_load(
        self, session: AsyncSession, plaintext: str,
    ) -> tuple[ApiKey, User] | None:
        if not plaintext or (not plaintext.startswith(API_KEY_LIVE_PREFIX) and not plaintext.startswith(API_KEY_TEST_PREFIX)):
            return None
        h = hash_api_key(plaintext)
        row = (
            await session.execute(
                select(ApiKey).where(
                    ApiKey.key_hash == h, ApiKey.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if row.expires_at and row.expires_at < datetime.now(tz=UTC):
            return None
        user = await session.get(User, row.user_id)
        if user is None or not user.is_active:
            return None
        return row, user

    async def update_last_used(
        self, session: AsyncSession, key_id: uuid.UUID, ip: str | None = None,
    ) -> None:
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .values(
                last_used_at=datetime.now(tz=UTC),
                last_used_ip=ip,
                use_count=ApiKey.use_count + 1,
            )
        )

    @staticmethod
    def _coerce(user_id: uuid.UUID | str) -> uuid.UUID:
        if isinstance(user_id, uuid.UUID):
            return user_id
        return uuid.UUID(str(user_id))


# Helper: module-level function used by the create_api_key script
async def create_key_for_user(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
    description: str | None = None,
    scopes: list[str] | None = None,
    expires_in_days: int | None = None,
) -> dict[str, Any]:
    from datetime import timedelta
    expires_at = (
        datetime.now(tz=UTC) + timedelta(days=expires_in_days)
        if expires_in_days
        else None
    )
    svc = ApiKeyService(session)
    row, plain = await svc.create(
        session, user_id,
        name=name,
        description=description,
        scopes=scopes,
        expires_at=expires_at,
    )
    return {
        "id": str(row.id),
        "plain": plain,
        "prefix": row.key_prefix,
        "last4": row.key_last4,
        "scopes": row.scopes,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


__all__ = ["ApiKeyService", "create_key_for_user"]
