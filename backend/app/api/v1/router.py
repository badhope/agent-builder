"""v1 API root router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    auth,
    batch,
    convert,
    email_verify,
    files,
    formats,
    password_reset,
    tasks,
    totp,
    users,
    webhooks,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(
    password_reset.router, prefix="/auth/password", tags=["auth"],
)
api_v1_router.include_router(
    email_verify.router, prefix="/auth/email", tags=["auth"],
)
api_v1_router.include_router(totp.router, prefix="/auth/totp", tags=["auth"])
api_v1_router.include_router(users.router, prefix="/users", tags=["users"])
api_v1_router.include_router(files.router, prefix="/files", tags=["files"])
api_v1_router.include_router(convert.router, prefix="/convert", tags=["convert"])
api_v1_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_v1_router.include_router(batch.router, prefix="/batches", tags=["batches"])
api_v1_router.include_router(formats.router, prefix="/formats", tags=["formats"])
api_v1_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_v1_router.include_router(admin.router, prefix="/admin", tags=["admin"])


__all__ = ["api_v1_router"]
