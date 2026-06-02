"""TOTP service tests.

Exercises enrollment, confirm, code verification, and disable flows.
"""

from __future__ import annotations

import uuid

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.totp_service import TotpService


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _mk_user(db_session: AsyncSession):
    from app.services.user_service import UserService
    from app.db.models.user import UserPlan

    svc = UserService(db_session)
    return await svc.create(
        email=f"totp+{uuid.uuid4().hex[:8]}@example.com",
        password="x" * 20,
        plan=UserPlan.ENTERPRISE,
    )


async def test_enroll_returns_secret_and_recovery_codes(
    db_session: AsyncSession,
) -> None:
    user = await _mk_user(db_session)
    svc = TotpService(db_session)
    enrollment = await svc.enroll(user, issuer="TestApp")
    assert enrollment.secret_base32
    assert len(enrollment.recovery_codes) == 10
    assert user.totp_enabled is False  # only confirmed after verify
    assert user.recovery_codes_hash  # stored as JSONB list of SHA-256 hashes


async def test_confirm_activates_totp(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session)
    svc = TotpService(db_session)
    enrollment = await svc.enroll(user)
    # Compute the correct code from the secret
    code = pyotp.TOTP(enrollment.secret_base32).now()
    await svc.confirm(user, code=code)
    assert user.totp_enabled is True
    assert user.totp_enrolled_at is not None


async def test_confirm_wrong_code_fails(db_session: AsyncSession) -> None:
    from app.exceptions import ValidationError

    user = await _mk_user(db_session)
    svc = TotpService(db_session)
    enrollment = await svc.enroll(user)
    with pytest.raises(ValidationError):
        await svc.confirm(user, code="000000")


async def test_verify_login(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session)
    svc = TotpService(db_session)
    enrollment = await svc.enroll(user)
    code = pyotp.TOTP(enrollment.secret_base32).now()
    await svc.confirm(user, code=code)
    fresh = pyotp.TOTP(enrollment.secret_base32).now()
    assert await svc.verify_login(user, code=fresh) is True
    assert await svc.verify_login(user, code="000000") is False


async def test_disable_clears_state(db_session: AsyncSession) -> None:
    user = await _mk_user(db_session)
    svc = TotpService(db_session)
    enrollment = await svc.enroll(user)
    code = pyotp.TOTP(enrollment.secret_base32).now()
    await svc.confirm(user, code=code)
    assert user.totp_enabled is True
    await svc.disable(user, password_confirm="x" * 20)
    assert user.totp_enabled is False
    assert user.totp_enrolled_at is None
    assert not user.recovery_codes_hash
