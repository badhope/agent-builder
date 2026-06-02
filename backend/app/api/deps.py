"""Authentication and authorisation FastAPI dependencies.

Three primary auth schemes are supported:

1. **Bearer JWT** (browser session) — RS256-signed token from ``/v1/auth/login``.
2. **API Key** (``X-API-Key: dfc_live_...``) — long-lived, scoped to a user.
3. **Anonymous** — used only for explicitly public endpoints.

The :func:`get_current_principal` dependency yields a ``Principal``
object that contains the user, the source (``jwt`` / ``api_key`` / ``anon``),
and any relevant metadata. Endpoints that require a user call this
dependency; admin-only endpoints additionally call :func:`require_admin`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import (
    Permission,
    Role,
    default_permissions_for,
    role_for_user,
)
from app.core.security import (
    jwt_manager,
)
from app.db.models.api_key import ApiKey
from app.db.models.user import User
from app.db.session import get_db
from app.exceptions import AuthenticationError, AuthorizationError


class AuthSource(StrEnum):
    JWT = "jwt"
    API_KEY = "api_key"
    ANON = "anon"


@dataclass(slots=True, frozen=True)
class Principal:
    """The authenticated caller."""

    user: User | None
    source: AuthSource
    api_key: ApiKey | None = None
    permissions: frozenset[str] = frozenset()

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None

    @property
    def is_admin(self) -> bool:
        return bool(self.user and self.user.is_admin)

    @property
    def role(self) -> Role:
        if not self.user:
            return Role.ANON
        return role_for_user(is_admin=self.user.is_admin, is_active=self.user.is_active)

    @property
    def user_id(self) -> uuid.UUID | None:
        return self.user.id if self.user else None


# ---- Token extractors -------------------------------------------------------


async def _bearer_or_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> tuple[str | None, str | None]:
    """Return ``(bearer_token, api_key)`` extracted from headers."""
    bearer: str | None = None
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            bearer = token
    return bearer, x_api_key


# ---- Principal factory ------------------------------------------------------


async def get_current_principal(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(_bearer_or_api_key)] = (None, None),
) -> Principal:
    """Resolve the request's identity from JWT or API key."""
    bearer, api_key_plain = creds
    principal: Principal | None = None

    # 1. API key takes precedence (less clock-skew sensitive than JWT)
    if api_key_plain:
        principal = await _principal_from_api_key(db, api_key_plain)

    # 2. JWT
    if principal is None and bearer:
        principal = await _principal_from_jwt(db, bearer)

    # 3. Anonymous
    if principal is None:
        principal = Principal(user=None, source=AuthSource.ANON, permissions=frozenset())

    # Stash for rate-limiter and audit log middleware
    request.state.user_id = principal.user_id
    request.state.api_key_id = principal.api_key.id if principal.api_key else None
    request.state.auth_source = principal.source.value

    return principal


async def require_user(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> User:
    if not principal.user:
        raise AuthenticationError("Authentication required.")
    if not principal.user.is_active:
        raise AuthenticationError("User account is disabled.", code="ACCOUNT_DISABLED")
    return principal.user


async def require_admin(
    user: Annotated[User, Depends(require_user)],
) -> User:
    if not user.is_admin:
        raise AuthorizationError("Admin privileges required.", code="ADMIN_REQUIRED")
    return user


async def require_permission(permission: Permission):
    """Return a dependency that asserts the principal has ``permission``."""

    async def _checker(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if not principal.user:
            raise AuthenticationError("Authentication required.")
        if permission.value not in principal.permissions:
            raise AuthorizationError(
                f"Missing permission: {permission.value}",
                code="PERMISSION_DENIED",
            )
        return principal

    return _checker


# ---- Internal helpers -------------------------------------------------------


async def _principal_from_jwt(db: AsyncSession, token: str) -> Principal | None:
    try:
        claims = jwt_manager.verify_token(token, expected_type="access")
    except AuthenticationError:
        return None
    sub = claims.get("sub")
    if not sub:
        return None
    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        return None

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        return None

    role = role_for_user(is_admin=user.is_admin, is_active=user.is_active)
    perms = frozenset(default_permissions_for(role))
    return Principal(user=user, source=AuthSource.JWT, permissions=perms)


async def _principal_from_api_key(db: AsyncSession, key: str) -> Principal | None:
    from app.services.api_key_service import ApiKeyService
    pair = await ApiKeyService(db).verify_and_load(db, key)
    if pair is None:
        return None
    row, user = pair
    # Touch last_used / use_count
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == row.id)
        .values(
            last_used_at=datetime.now(tz=UTC),
            use_count=ApiKey.use_count + 1,
        )
    )

    role = role_for_user(is_admin=user.is_admin, is_active=user.is_active)
    allowed = set(default_permissions_for(role))
    # The key's scopes are an upper bound; admin keys override
    if row.scopes:
        allowed = {p for p in row.scopes if p in allowed or user.is_admin}
    perms = frozenset(allowed)

    return Principal(
        user=user,
        source=AuthSource.API_KEY,
        api_key=row,
        permissions=perms,
    )


__all__ = [
    "AuthSource",
    "Principal",
    "get_current_principal",
    "require_admin",
    "require_permission",
    "require_user",
]
