"""Auth-related Pydantic schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PW_MIN = 12
PW_MAX = 256


def _validate_password(v: str) -> str:
    if len(v) < PW_MIN:
        raise ValueError(f"Password must be at least {PW_MIN} characters.")
    if len(v) > PW_MAX:
        raise ValueError(f"Password must be at most {PW_MAX} characters.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain an uppercase letter.")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain a lowercase letter.")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain a digit.")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Password must contain a symbol.")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PW_MIN, max_length=PW_MAX)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def _check_pw(cls, v: str) -> str:
        return _validate_password(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PW_MAX)
    totp_code: str | None = Field(default=None, min_length=6, max_length=10)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token_jti: str = Field(min_length=4, max_length=64)


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=PW_MAX)
    new_password: str = Field(min_length=PW_MIN, max_length=PW_MAX)

    @field_validator("new_password")
    @classmethod
    def _check_pw(cls, v: str) -> str:
        return _validate_password(v)


class PasswordResetRequest(BaseModel):
    """Step 1: ask for a reset link to be emailed."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Step 2: redeem the token and set a new password."""

    token: str = Field(min_length=20)
    new_password: str = Field(min_length=PW_MIN, max_length=PW_MAX)

    @field_validator("new_password")
    @classmethod
    def _check_pw(cls, v: str) -> str:
        return _validate_password(v)


class EmailVerifyRequest(BaseModel):
    token: str = Field(min_length=20)


class TokenPair(BaseModel):
    """Both access and refresh tokens, plus expiry."""

    access_token: str
    refresh_token: str
    refresh_jti: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str = "user"


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserRead(BaseModel):
    """Public user representation (no password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    role: str
    plan: str
    is_active: bool
    is_verified: bool
    is_admin: bool
    totp_enabled: bool
    last_login_at: datetime | None
    quota_conversions_per_day: int
    quota_storage_mb: int
    quota_max_file_size_mb: int
    quota_concurrent_tasks: int
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500)
    preferences: dict | None = None


class UserAdminUpdate(BaseModel):
    role: str | None = None
    plan: str | None = None
    is_active: bool | None = None
    is_verified: bool | None = None
    quota_conversions_per_day: int | None = Field(default=None, ge=0)
    quota_storage_mb: int | None = Field(default=None, ge=0)
    quota_max_file_size_mb: int | None = Field(default=None, ge=0)
    quota_concurrent_tasks: int | None = Field(default=None, ge=0)


# ---- API keys --------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyCreated(BaseModel):
    id: uuid.UUID
    name: str | None
    plain: str  # ONLY returned on creation
    prefix: str
    last4: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    description: str | None
    prefix: str
    last4: str
    scopes: list[str]
    last_used_at: datetime | None
    last_used_ip: str | None
    use_count: int
    expires_at: datetime | None
    is_active: bool
    revoked_at: datetime | None
    revoked_reason: str | None
    created_at: datetime


# ---- 2FA -------------------------------------------------------------------


class TotpEnrollRequest(BaseModel):
    """Start enrollment — the server returns a secret + otpauth URL."""


class TotpEnrollResponse(BaseModel):
    secret: str  # base32
    otpauth_url: str
    recovery_codes: list[str]  # 10 single-use recovery codes


class TotpConfirmRequest(BaseModel):
    """Verify a 6-digit code from the user's authenticator to confirm enrollment."""

    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TotpDisableRequest(BaseModel):
    password: str = Field(min_length=1)
    code: str = Field(min_length=6, max_length=10)


class TotpStatus(BaseModel):
    enabled: bool
    enrolled_at: datetime | None
    recovery_codes_remaining: int
