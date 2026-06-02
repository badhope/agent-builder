"""TOTP / 2FA routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import Principal, require_user
from app.db.session import db_session
from app.schemas.auth import (
    TotpConfirmRequest,
    TotpDisableRequest,
    TotpEnrollResponse,
    TotpStatus,
)
from app.services.totp_service import TotpService

router = APIRouter()


@router.post("/enroll", response_model=TotpEnrollResponse)
async def enroll(principal: Principal = Depends(require_user)):
    async with db_session() as session:
        ts = TotpService(session)
        enrollment = await ts.enroll(principal.user)  # type: ignore[arg-type]
    return TotpEnrollResponse(
        secret=enrollment.secret_base32,
        otpauth_url=enrollment.otpauth_url,
        recovery_codes=enrollment.recovery_codes,
    )


@router.post("/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm(
    payload: TotpConfirmRequest, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        ts = TotpService(session)
        await ts.confirm(principal.user, payload.code)  # type: ignore[arg-type]


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable(
    payload: TotpDisableRequest, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        ts = TotpService(session)
        await ts.disable(  # type: ignore[arg-type]
            principal.user, payload.password, payload.code,
        )


@router.get("/status", response_model=TotpStatus)
async def status_(principal: Principal = Depends(require_user)):
    user = principal.user
    return TotpStatus(
        enabled=bool(user and user.totp_enabled),
        enrolled_at=user.totp_enrolled_at if user else None,
        recovery_codes_remaining=len(user.recovery_codes_hash) if user else 0,
    )


__all__ = ["router"]
