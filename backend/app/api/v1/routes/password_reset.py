"""Password reset routes."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.db.session import db_session
from app.schemas.auth import PasswordResetConfirm, PasswordResetRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot(payload: PasswordResetRequest):
    async with db_session() as session:
        auth = AuthService(session)
        await auth.forgot_password(payload.email)
    return {"detail": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset(payload: PasswordResetConfirm):
    async with db_session() as session:
        auth = AuthService(session)
        await auth.reset_password(payload.token, payload.new_password)


__all__ = ["router"]
