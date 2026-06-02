"""Password reset flow tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _mk_user(db_session: AsyncSession):
    from app.services.user_service import UserService
    from app.db.models.user import UserPlan

    svc = UserService(db_session)
    return await svc.create(
        email=f"reset+{uuid.uuid4().hex[:8]}@example.com",
        password="OldPassword1!",
        plan=UserPlan.PRO,
    )


async def test_forgot_then_reset_succeeds(db_session: AsyncSession) -> None:
    from app.services.auth_service import AuthService

    auth = AuthService(db_session)
    user = await _mk_user(db_session)
    token = await auth.issue_password_reset_token(user)
    # Old password works
    assert await auth.verify_credentials(user.email, "OldPassword1!") is not None
    # Reset
    new_pw = "BrandNewPassword2!"
    assert await auth.consume_password_reset_token(token.raw_token, new_pw) is True
    # Old password no longer works
    assert await auth.verify_credentials(user.email, "OldPassword1!") is None
    # New password works
    assert await auth.verify_credentials(user.email, new_pw) is not None


async def test_reset_token_single_use(db_session: AsyncSession) -> None:
    from app.services.auth_service import AuthService

    auth = AuthService(db_session)
    user = await _mk_user(db_session)
    token = await auth.issue_password_reset_token(user)
    assert await auth.consume_password_reset_token(token.raw_token, "Abcd1234!") is True
    assert await auth.consume_password_reset_token(token.raw_token, "Abcd1234!") is False


async def test_reset_token_too_weak_rejected(db_session: AsyncSession) -> None:
    from app.exceptions import ValidationError
    from app.services.auth_service import AuthService

    auth = AuthService(db_session)
    user = await _mk_user(db_session)
    token = await auth.issue_password_reset_token(user)
    with pytest.raises(ValidationError):
        await auth.consume_password_reset_token(token.raw_token, "x")
