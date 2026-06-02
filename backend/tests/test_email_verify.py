"""Email verification flow tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_verification_token
from app.db.models.user import UserPlan
from app.db.models.verification_token import TokenPurpose, VerificationToken

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _mk_user(db_session: AsyncSession, *, verified: bool = False):
    from app.services.user_service import UserService

    svc = UserService(db_session)
    user = await svc.create(
        email=f"verify+{uuid.uuid4().hex[:8]}@example.com",
        password="x" * 20,
        plan=UserPlan.PRO,
    )
    if verified:
        user.is_verified = True
        user.email_verified_at = datetime.now(tz=UTC)
        await db_session.flush()
    return user


async def _mk_token(db_session: AsyncSession, user_id: uuid.UUID, *, ttl: timedelta = timedelta(days=2)):
    token_plain, token_hash = generate_verification_token()
    row = VerificationToken(
        id=uuid.uuid4(),
        user_id=user_id,
        purpose=TokenPurpose.EMAIL_VERIFY,
        token_hash=token_hash,
        token_prefix=token_plain[:12],
        context={"email": "test@example.com"},
        expires_at=datetime.now(tz=UTC) + ttl,
    )
    db_session.add(row)
    await db_session.flush()
    return token_plain


async def test_register_then_resend_then_verify(db_session: AsyncSession) -> None:
    from app.services.auth_service import AuthService

    auth = AuthService(db_session)
    user, _tokens = await auth.register(
        email=f"new+{uuid.uuid4().hex[:8]}@example.com",
        password="x" * 20,
        full_name="New User",
    )
    assert user.is_verified is False

    token_plain = await _mk_token(db_session, user.id)
    assert token_plain

    await auth.verify_email(token_plain)
    assert user.is_verified is True


async def test_consume_token_only_once(db_session: AsyncSession) -> None:
    from app.services.auth_service import AuthService

    auth = AuthService(db_session)
    user = await _mk_user(db_session)
    token_plain = await _mk_token(db_session, user.id)

    await auth.verify_email(token_plain)
    assert user.is_verified is True

    import pytest
    from app.exceptions import AuthenticationError

    with pytest.raises(AuthenticationError):
        await auth.verify_email(token_plain)


async def test_expired_token_rejected(db_session: AsyncSession) -> None:
    from app.services.auth_service import AuthService

    auth = AuthService(db_session)
    user = await _mk_user(db_session)
    token_plain = await _mk_token(db_session, user.id, ttl=timedelta(seconds=-1))

    import pytest
    from app.exceptions import AuthenticationError

    with pytest.raises(AuthenticationError):
        await auth.verify_email(token_plain)