"""Email verification routes."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.db.session import db_session
from app.schemas.auth import EmailVerifyRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify(payload: EmailVerifyRequest):
    async with db_session() as session:
        auth = AuthService(session)
        await auth.verify_email(payload.token)


@router.post("/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend(principal_email: str):
    """Resend a verification email (best-effort)."""
    async with db_session() as session:
        auth = AuthService(session)
        user = await auth.users.get_by_email(principal_email)
        if user is not None:
            await auth._issue_email_verify(user)
    return {"detail": "If the account exists, a new link has been sent."}


__all__ = ["router"]
