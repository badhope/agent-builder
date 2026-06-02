"""TOTP / 2FA service.

Wraps the low-level :mod:`app.core.security` helpers and the persisted
``User`` row to provide an end-to-end flow:

* ``enroll`` — issue a fresh secret + recovery codes (DB stored as Fernet
  ciphertext for the secret and SHA-256 hashes for the recovery codes).
* ``confirm`` — verify a 6-digit code to flip ``totp_enabled`` on.
* ``verify_login`` — verify a code on the login path; consume a recovery
  code if needed.
* ``disable`` — turn 2FA off (requires password + a fresh code).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    build_otpauth_url,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_code,
    verify_totp,
)
from app.db.models.user import User
from app.exceptions import AuthenticationError, ValidationError

ISSUER = "DocFormatConverter"


@dataclass(slots=True, frozen=True)
class TotpEnrollment:
    secret_base32: str
    otpauth_url: str
    recovery_codes: list[str]


class TotpService:
    """All 2FA flows for a user."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enroll(self, user: User) -> TotpEnrollment:
        if user.totp_enabled:
            raise ValidationError("2FA is already enabled.", code="TOTP_ALREADY_ENABLED")
        secret = generate_totp_secret()
        otpauth = build_otpauth_url(secret, user.email, issuer=ISSUER)
        codes = generate_recovery_codes(10)
        # Stash *pending* values on the user (encrypted secret, hashed codes)
        user.totp_secret_enc = encrypt_secret(secret)
        # Pre-store recovery codes (hashed); they are revealed once and can be
        # used immediately, but the secret only becomes active after confirm.
        user.recovery_codes_hash = [hash_recovery_code(c) for c in codes]
        await self.session.flush()
        return TotpEnrollment(
            secret_base32=secret,
            otpauth_url=otpauth,
            recovery_codes=codes,
        )

    async def confirm(self, user: User, code: str) -> None:
        if not user.totp_secret_enc:
            raise ValidationError("No 2FA enrollment in progress.", code="TOTP_NOT_ENROLLED")
        if user.totp_enabled:
            raise ValidationError("2FA is already enabled.", code="TOTP_ALREADY_ENABLED")
        secret = decrypt_secret(user.totp_secret_enc)
        if not verify_totp(secret, code):
            raise AuthenticationError("Invalid authenticator code.", code="TOTP_INVALID")
        user.totp_enabled = True
        user.totp_enrolled_at = datetime.now(tz=UTC)
        await self.session.flush()

    async def disable(self, user: User, password: str, code: str) -> None:
        from app.core.security import password_manager
        if not password_manager.verify(password, user.password_hash):
            raise AuthenticationError("Invalid password.", code="INVALID_PASSWORD")
        if not user.totp_enabled or not user.totp_secret_enc:
            raise ValidationError("2FA is not enabled.", code="TOTP_NOT_ENABLED")
        secret = decrypt_secret(user.totp_secret_enc)
        # Accept either TOTP or a recovery code
        ok = verify_totp(secret, code) or self._consume_recovery_code(user, code)
        if not ok:
            raise AuthenticationError("Invalid authenticator code.", code="TOTP_INVALID")
        user.totp_enabled = False
        user.totp_secret_enc = None
        user.totp_enrolled_at = None
        user.recovery_codes_hash = []
        await self.session.flush()

    async def verify_login(self, user: User, code: str) -> bool:
        if not user.totp_enabled or not user.totp_secret_enc:
            return True  # 2FA not enabled — pass
        secret = decrypt_secret(user.totp_secret_enc)
        if verify_totp(secret, code):
            return True
        return self._consume_recovery_code(user, code)

    def _consume_recovery_code(self, user: User, code: str) -> bool:
        if not user.recovery_codes_hash:
            return False
        target = hash_recovery_code(code)
        if target not in user.recovery_codes_hash:
            return False
        user.recovery_codes_hash = [
            h for h in user.recovery_codes_hash if h != target
        ]
        return True


totp_service_holder: dict[uuid.UUID, TotpService] = {}


__all__ = ["TotpEnrollment", "TotpService"]
