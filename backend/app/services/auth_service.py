"""Authentication service.

Provides high-level flows consumed by the routes:

* ``register``     — create a user + issue a token pair.
* ``login``        — verify password (+ optional TOTP), issue tokens.
* ``refresh``      — rotate tokens using a valid refresh token.
* ``logout``       — record a refresh-jti revocation (best-effort).
* ``change_password``
* ``forgot_password`` / ``reset_password``
* ``verify_email``
* ``bootstrap_admin`` — idempotent first-start admin user.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_verification_token,
    jwt_manager,
    password_manager,
)
from app.db.models.revoked_token import RevokedToken
from app.db.models.user import User, UserPlan, UserRole
from app.db.models.verification_token import TokenPurpose, VerificationToken
from app.db.session import db_session
from app.exceptions import AuthenticationError, NotFoundError
from app.logging_config import get_logger
from app.services.email_service import email_service
from app.services.user_service import UserService

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserService(session)

    # ---- registration ----

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> tuple[User, TokenPair]:
        user = await self.users.create(
            email=email,
            password=password,
            full_name=full_name,
        )
        # Send email verification token (best-effort)
        await self._issue_email_verify(user)
        tokens = self._issue_tokens(user)
        return user, tokens

    # ---- login ----

    async def login(
        self,
        *,
        email: str,
        password: str,
        totp_code: str | None = None,
        ip: str | None = None,
    ) -> TokenPair:
        user = await self.users.get_by_email(email)
        # Constant-time-ish dummy verify when user missing
        if user is None or not user.is_active:
            password_manager.verify(password, _DUMMY_HASH)
            raise AuthenticationError("Invalid credentials.", code="INVALID_CREDENTIALS")
        if not password_manager.verify(password, user.password_hash):
            raise AuthenticationError("Invalid credentials.", code="INVALID_CREDENTIALS")
        # Opportunistic rehash
        if password_manager.needs_rehash(user.password_hash):
            user.password_hash = password_manager.hash(password)
        # 2FA check
        if user.totp_enabled:
            if not totp_code:
                raise AuthenticationError("2FA code required.", code="TOTP_REQUIRED")
            from app.services.totp_service import TotpService
            ts = TotpService(self.session)
            if not await ts.verify_login(user, totp_code):
                raise AuthenticationError("Invalid 2FA code.", code="TOTP_INVALID")
        await self.users.touch_last_login(user, ip=ip)
        await self.session.flush()
        return self._issue_tokens(user)

    # ---- refresh / logout ----

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            claims = jwt_manager.verify_token(refresh_token, expected_type="refresh")
        except AuthenticationError as exc:
            raise AuthenticationError(
                "Invalid refresh token.", code="INVALID_REFRESH",
            ) from exc
        sub = claims.get("sub")
        jti = claims.get("jti")
        if not sub or not jti:
            raise AuthenticationError("Invalid refresh token.", code="INVALID_REFRESH")
        # SECURITY: Reject tokens whose JTI has been revoked (logout,
        # password change, admin revoke).
        if await self._is_jti_revoked(jti):
            raise AuthenticationError(
                "Refresh token has been revoked.", code="REVOKED_REFRESH",
            )
        user = await self.users.get_by_id(sub)
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or disabled.", code="USER_INACTIVE")
        return self._issue_tokens(user, refresh_jti_hint=jti)

    async def logout(self, refresh_jti: str, principal: Any) -> None:
        # SECURITY: Persist the JTI as revoked so it cannot be reused.
        # Without this, a stolen refresh token would remain valid for
        # refresh_ttl_day (default 30 days).
        await self._revoke_jti(
            refresh_jti,
            user_id=principal.user_id if principal else None,
            reason="logout",
        )
        logger.info(
            "auth.logout",
            user_id=str(principal.user_id) if principal and principal.user_id else None,
            jti=refresh_jti[:12] + "…",
        )

    async def _is_jti_revoked(self, jti: str) -> bool:
        """Check if a JTI has been explicitly revoked."""
        from sqlalchemy import select
        result = await self.session.execute(
            select(RevokedToken.jti).where(RevokedToken.jti == jti).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _revoke_jti(self, jti: str, *, user_id: Any = None, reason: str = "logout") -> None:
        """Persist a JTI revocation. Idempotent (primary key = jti)."""
        if not jti:
            return
        # Compute the natural expiry from the JWT itself.
        import jwt as pyjwt
        from datetime import UTC, datetime, timedelta
        exp = None
        try:
            unverified = pyjwt.decode(
                jti,
                options={"verify_signature": False, "verify_exp": False},
            )
            exp = unverified.get("exp")
        except Exception:  # noqa: BLE001 - best effort
            exp = None
        expires_at = (
            datetime.fromtimestamp(int(exp), tz=UTC)
            if exp
            else datetime.now(tz=UTC) + timedelta(days=30)
        )
        existing = await self.session.execute(
            select(RevokedToken).where(RevokedToken.jti == jti).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return  # already revoked
        self.session.add(
            RevokedToken(
                jti=jti,
                user_id=user_id,
                reason=reason,
                expires_at=expires_at,
            )
        )
        await self.session.flush()

    # ---- password change / reset ----

    async def change_password(
        self,
        *,
        user_id: uuid.UUID | str,
        old_password: str,
        new_password: str,
    ) -> None:
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid user.", code="INVALID_CREDENTIALS")
        if not password_manager.verify(old_password, user.password_hash):
            raise AuthenticationError("Invalid password.", code="INVALID_CREDENTIALS")
        user.password_hash = password_manager.hash(new_password)
        await self.session.flush()

    async def forgot_password(self, email: str) -> None:
        # Always 200 to avoid email enumeration
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active:
            logger.info("auth.forgot_password_unknown_email", email=email)
            return
        token_plain, token_hash = generate_verification_token()
        row = VerificationToken(
            id=uuid.uuid4(),
            user_id=user.id,
            purpose=TokenPurpose.PASSWORD_RESET,
            token_hash=token_hash,
            token_prefix=token_plain[:12],
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )
        self.session.add(row)
        await self.session.flush()
        # Send email (best-effort)
        await email_service.send_email(
            to=user.email,
            subject="Reset your password",
            template="password_reset",
            context={"reset_url": f"/reset?token={token_plain}", "user": user},
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        import hashlib
        h = hashlib.sha256(token.encode("utf-8")).hexdigest()
        stmt = select(VerificationToken).where(
            VerificationToken.token_hash == h,
            VerificationToken.purpose == TokenPurpose.PASSWORD_RESET,
            VerificationToken.consumed_at.is_(None),
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise AuthenticationError("Invalid or expired token.", code="INVALID_RESET_TOKEN")
        if row.expires_at < datetime.now(tz=UTC):
            raise AuthenticationError("Token has expired.", code="RESET_TOKEN_EXPIRED")
        user = await self.users.get_by_id(row.user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        user.password_hash = password_manager.hash(new_password)
        row.consumed_at = datetime.now(tz=UTC)
        await self.session.flush()

    # ---- email verification ----

    async def _issue_email_verify(self, user: User) -> None:
        token_plain, token_hash = generate_verification_token()
        row = VerificationToken(
            id=uuid.uuid4(),
            user_id=user.id,
            purpose=TokenPurpose.EMAIL_VERIFY,
            token_hash=token_hash,
            token_prefix=token_plain[:12],
            context={"email": user.email},
            expires_at=datetime.now(tz=UTC) + timedelta(days=2),
        )
        self.session.add(row)
        await self.session.flush()
        await email_service.send_email(
            to=user.email,
            subject="Verify your email",
            template="email_verify",
            context={"verify_url": f"/verify?token={token_plain}", "user": user},
        )

    async def verify_email(self, token: str) -> None:
        import hashlib
        h = hashlib.sha256(token.encode("utf-8")).hexdigest()
        stmt = select(VerificationToken).where(
            VerificationToken.token_hash == h,
            VerificationToken.purpose == TokenPurpose.EMAIL_VERIFY,
            VerificationToken.consumed_at.is_(None),
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise AuthenticationError("Invalid or expired token.", code="INVALID_VERIFY_TOKEN")
        if row.expires_at < datetime.now(tz=UTC):
            raise AuthenticationError("Token has expired.", code="VERIFY_TOKEN_EXPIRED")
        user = await self.users.get_by_id(row.user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        user.is_verified = True
        user.email_verified_at = datetime.now(tz=UTC)
        row.consumed_at = datetime.now(tz=UTC)
        await self.session.flush()

    # ---- token issuance ----

    def _issue_tokens(
        self, user: User, *, refresh_jti_hint: str | None = None,
    ) -> TokenPair:
        access, access_exp = jwt_manager.issue_access_token(
            user_id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            role=user.role.value,
            plan=user.plan.value,
        )
        refresh, jti, _ = jwt_manager.issue_refresh_token(user_id=user.id)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            refresh_jti=jti,
            expires_in=max(
                0, int((access_exp - datetime.now(tz=UTC)).total_seconds())
            ),
        )


# ---- TokenPair (value object kept here to avoid an import cycle) ----


@dataclass(slots=True, frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    refresh_jti: str
    expires_in: int
    token_type: str = "Bearer"
    scope: str = "user"

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "refresh_jti": self.refresh_jti,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
        }


# Module-level dummy hash (valid Argon2id format) to keep timing constant
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "c29tZXNhbHRzdHJpbmcxMjM$"
    "0000000000000000000000000000000000000000000"
)


async def bootstrap_admin() -> None:
    """Create the bootstrap admin on first start (idempotent)."""
    from app.settings import get_settings
    settings = get_settings()
    if not settings.bootstrap.enabled:
        return
    try:
        async with db_session() as session:
            svc = UserService(session)
            existing = await svc.get_by_email(settings.bootstrap.email)
            if existing is not None:
                return
            await svc.create(
                email=settings.bootstrap.email,
                password=settings.bootstrap.password.get_secret_value(),
                full_name="Bootstrap Admin",
                is_admin=True,
                role=UserRole.ADMIN,
                plan=UserPlan.ENTERPRISE,
            )
            logger.info(
                "bootstrap.admin_created",
                email=settings.bootstrap.email,
            )
    except Exception as exc:
        logger.warning("bootstrap.admin_failed", error=str(exc))


__all__ = ["AuthService", "TokenPair", "bootstrap_admin"]
