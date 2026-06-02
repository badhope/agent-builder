"""Security primitives.

Includes:
* Argon2id password hashing (OWASP 2024 parameters).
* RS256 JWT issuing + verification (auto-generates keys in dev).
* API Key generation, hashing, constant-time comparison.
* Webhook payload HMAC signing / verification.
* ``SignedTokenIssuer`` for short-lived download tokens.
* Fernet symmetric encryption for at-rest secrets (TOTP, recovery codes).
* TOTP / HOTP code generation and verification.
* Recovery code generation and hashing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.exceptions import AppError, AuthenticationError
from app.logging_config import get_logger
from app.settings import get_settings

logger = get_logger(__name__)


# =============================================================================
# Password hashing (Argon2id)
# =============================================================================


class PasswordManager:
    """Argon2id password hashing."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3, memory_cost=64 * 1024, parallelism=4,
            hash_len=32, salt_len=16,
        )

    def hash(self, password: str) -> str:
        if not password or len(password) < 8:
            raise AppError(
                "Password must be at least 8 characters.",
                code="WEAK_PASSWORD", status_code=400,
            )
        return self._hasher.hash(password)

    def verify(self, password: str, encoded_hash: str) -> bool:
        if not password or not encoded_hash:
            return False
        try:
            return self._hasher.verify(encoded_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded_hash)
        except InvalidHashError:
            return True


password_manager = PasswordManager()


# =============================================================================
# API Key generation, hashing, verification
# =============================================================================


API_KEY_PREFIX = "dck_"
API_KEY_LIVE_PREFIX = "dck_live_"
API_KEY_TEST_PREFIX = "dck_test_"


@dataclass(frozen=True, slots=True)
class GeneratedApiKey:
    plaintext: str
    hash: str
    prefix: str
    last4: str


def generate_api_key(test_mode: bool = False) -> GeneratedApiKey:
    """Generate a fresh API key. The plaintext is shown once; only ``hash``
    is persisted.
    """
    raw = secrets.token_urlsafe(32)
    prefix = API_KEY_TEST_PREFIX if test_mode else API_KEY_LIVE_PREFIX
    plaintext = f"{prefix}{raw}"
    return GeneratedApiKey(
        plaintext=plaintext,
        hash=hash_api_key(plaintext),
        prefix=prefix,
        last4=plaintext[-4:],
    )


def hash_api_key(plaintext: str) -> str:
    """Return the canonical hex SHA-256 of an API key."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def verify_api_key(plaintext: str, key_hash: str) -> bool:
    return hmac.compare_digest(
        hash_api_key(plaintext).encode(), key_hash.encode()
    )


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# =============================================================================
# JWT (RS256) — asymmetric, supports multi-service verification
# =============================================================================


class JwtManager:
    """Issues and verifies RS256 JWTs.

    On instantiation:
      1. Reads ``JWT_PRIVATE_KEY_PATH`` / ``JWT_PUBLIC_KEY_PATH`` from settings.
      2. If a private key exists, loads it; else, if ``auto_generate_keys``
         is true, generates a new 4096-bit key pair (dev convenience).
      3. Caches the public key (a copy of which is safe to expose to other
         services for verification).
    """

    def __init__(self) -> None:
        s = get_settings().jwt
        if s.algorithm != "RS256":
            raise RuntimeError(
                f"Only RS256 is supported, got {s.algorithm!r}. "
                "Symmetric algorithms must not be used for JWT."
            )
        self._settings = s
        self._private_key = self._load_or_generate_private()
        self._public_key = self._load_or_generate_public()

    @property
    def public_key_pem(self) -> bytes:
        return self._public_key

    @property
    def private_key_pem(self) -> bytes:
        return self._private_key

    def _load_or_generate_private(self) -> bytes:
        path = Path(self._settings.private_key_path)
        if path.exists():
            return path.read_bytes()
        if not self._settings.auto_generate_keys:
            raise FileNotFoundError(
                f"JWT private key not found at {path} and auto_generate_keys is false"
            )
        logger.warning("jwt.auto_generating_keys", path=str(path))
        return self._generate_and_persist_keypair()

    def _load_or_generate_public(self) -> bytes:
        path = Path(self._settings.public_key_path)
        if path.exists():
            return path.read_bytes()
        priv = serialization.load_pem_private_key(self._private_key, password=None)
        pub = priv.public_key()  # type: ignore[attr-defined]
        pem = pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pem)
        return pem

    def _generate_and_persist_keypair(self) -> bytes:
        priv = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        priv_path = Path(self._settings.private_key_path)
        priv_path.parent.mkdir(parents=True, exist_ok=True)
        priv_path.write_bytes(priv_pem)
        try:
            priv_path.chmod(0o600)
        except OSError:
            pass
        Path(self._settings.public_key_path).write_bytes(pub_pem)
        return priv_pem

    # -- Issue / verify ---------------------------------------------------

    def issue_access_token(
        self,
        user_id: uuid.UUID | str,
        *,
        email: str | None = None,
        is_admin: bool = False,
        role: str | None = None,
        plan: str | None = None,
        scopes: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> tuple[str, datetime]:
        """Return ``(token, expires_at)`` for a new access token."""
        now = datetime.now(tz=UTC)
        exp = now + timedelta(minutes=self._settings.access_ttl_min)
        claims: dict[str, Any] = {
            "iss": self._settings.issuer,
            "aud": self._settings.audience,
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": secrets.token_urlsafe(16),
            "typ": "access",
        }
        if email:
            claims["email"] = email
        if is_admin:
            claims["is_admin"] = True
        if role:
            claims["role"] = role
        if plan:
            claims["plan"] = plan
        if scopes:
            claims["scopes"] = scopes
        if extra_claims:
            claims.update(extra_claims)
        token = jwt.encode(claims, self._private_key, algorithm="RS256")
        return token, exp

    def issue_refresh_token(
        self,
        user_id: uuid.UUID | str,
    ) -> tuple[str, str, datetime]:
        """Return ``(token, jti, expires_at)`` for a refresh token."""
        now = datetime.now(tz=UTC)
        exp = now + timedelta(days=self._settings.refresh_ttl_day)
        jti = secrets.token_urlsafe(24)
        claims = {
            "iss": self._settings.issuer,
            "aud": self._settings.audience,
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": jti,
            "typ": "refresh",
        }
        token = jwt.encode(claims, self._private_key, algorithm="RS256")
        return token, jti, exp

    def verify_token(self, token: str, *, expected_type: str | None = None) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Token has expired.", code="TOKEN_EXPIRED") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthenticationError("Invalid token audience.", code="INVALID_AUDIENCE") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationError("Invalid token issuer.", code="INVALID_ISSUER") from exc
        except jwt.InvalidTokenError as exc:
            logger.info("jwt.invalid_token", error=str(exc))
            raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc

        if expected_type and claims.get("typ") != expected_type:
            raise AuthenticationError(
                f"Expected token type {expected_type!r}, got {claims.get('typ')!r}.",
                code="WRONG_TOKEN_TYPE",
            )
        return claims

    def verify_token_for_user(
        self, token: str, *, user_id: uuid.UUID, expected_type: str
    ) -> dict[str, Any]:
        claims = self.verify_token(token, expected_type=expected_type)
        if claims.get("sub") != str(user_id):
            raise AuthenticationError("Token does not match the user.", code="TOKEN_USER_MISMATCH")
        return claims


jwt_manager = JwtManager()


# =============================================================================
# Webhook signing — per-user secret preferred, but signature format is
# identical to the global secret fallback.
# =============================================================================


def sign_webhook_payload(payload_bytes: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


# =============================================================================
# Signed download tokens
# =============================================================================


class SignedTokenIssuer:
    """Issues and verifies short-lived HMAC tokens for download URLs."""

    def __init__(self, secret: str | bytes | None = None) -> None:
        if secret is None:
            secret = get_settings().app_secret_key.get_secret_value()
        if isinstance(secret, str):
            secret = secret.encode()
        self._secret = secret

    def issue(
        self,
        *,
        subject: str,
        extra: dict[str, Any] | None = None,
        ttl_s: int = 3600,
    ) -> str:
        payload: dict[str, Any] = {
            "sub": subject,
            "exp": int(time.time()) + ttl_s,
            "jti": secrets.token_urlsafe(8),
        }
        if extra:
            payload.update(extra)
        body = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).rstrip(b"=")
        sig = hmac.new(self._secret, body, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=")
        return f"{body.decode()}.{sig_b64.decode()}"

    def verify(self, token: str) -> dict[str, Any]:
        try:
            body_b64, sig_b64 = token.rsplit(".", 1)
        except ValueError as exc:
            raise AuthenticationError("Malformed token.", code="MALFORMED_TOKEN") from exc

        body = base64.urlsafe_b64decode(body_b64 + "==")
        sig = base64.urlsafe_b64decode(sig_b64 + "==")
        expected = hmac.new(self._secret, body_b64.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, sig):
            raise AuthenticationError("Invalid token signature.", code="BAD_TOKEN_SIGNATURE")

        payload = json.loads(body)
        if int(payload.get("exp", 0)) < int(time.time()):
            raise AuthenticationError("Token has expired.", code="TOKEN_EXPIRED")
        return payload


# =============================================================================
# Fernet symmetric encryption (for TOTP secrets, recovery codes, etc.)
# =============================================================================


def _derive_fernet_key() -> bytes:
    """Derive a 32-byte Fernet key from the app secret (HKDF-like)."""
    secret = get_settings().app_secret_key.get_secret_value().encode()
    digest = hashlib.sha256(b"docconv-fernet:" + secret).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError("Invalid ciphertext.", code="DECRYPTION_FAILED", status_code=500) from exc


# =============================================================================
# TOTP / 2FA
# =============================================================================


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_otpauth_url(secret: str, email: str, issuer: str = "DocFormatConverter") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Return True if ``code`` matches the current TOTP for ``secret``."""
    if not secret or not code:
        return False
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=valid_window)
    except Exception:
        return False


def generate_recovery_codes(n: int = 10) -> list[str]:
    """Generate ``n`` single-use recovery codes formatted ``xxxx-xxxx-xxxx-xxxx``."""
    out: list[str] = []
    for _ in range(n):
        raw = secrets.token_hex(8)
        out.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}")
    return out


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.replace("-", "").lower().encode("utf-8")).hexdigest()


# =============================================================================
# Verification tokens (password reset, email verify, etc.)
# =============================================================================


def generate_verification_token() -> tuple[str, str]:
    """Return ``(plaintext, sha256_hash)`` for a verification token."""
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = [
    "API_KEY_LIVE_PREFIX",
    "API_KEY_PREFIX",
    "API_KEY_TEST_PREFIX",
    "GeneratedApiKey",
    "JwtManager",
    "PasswordManager",
    "SignedTokenIssuer",
    "build_otpauth_url",
    "constant_time_eq",
    "decrypt_secret",
    "encrypt_secret",
    "generate_api_key",
    "generate_recovery_codes",
    "generate_totp_secret",
    "generate_verification_token",
    "hash_api_key",
    "hash_recovery_code",
    "jwt_manager",
    "password_manager",
    "sign_webhook_payload",
    "verify_api_key",
    "verify_totp",
    "verify_webhook_signature",
]
