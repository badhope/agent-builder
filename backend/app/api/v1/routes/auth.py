"""Auth routes: register, login, refresh, logout, password change, API keys."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import Principal, get_current_principal, require_user
from app.db.session import db_session
from app.schemas.auth import (
    AccessToken,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRead,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserRead,
)
from app.services import api_key_service, auth_service

router = APIRouter()


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    async with db_session() as session:
        auth = auth_service.AuthService(session)
        _user, tokens = await auth.register(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    return tokens.to_dict()


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, request: Request):
    ip = request.client.host if request.client else None
    async with db_session() as session:
        auth = auth_service.AuthService(session)
        tokens = await auth.login(
            email=payload.email,
            password=payload.password,
            totp_code=payload.totp_code,
            ip=ip,
        )
    return tokens.to_dict()


@router.post("/refresh", response_model=AccessToken)
async def refresh(payload: RefreshRequest):
    async with db_session() as session:
        auth = auth_service.AuthService(session)
        tokens = await auth.refresh(payload.refresh_token)
    return {
        "access_token": tokens.access_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, principal: Principal = Depends(get_current_principal)):
    async with db_session() as session:
        auth = auth_service.AuthService(session)
        await auth.logout(payload.refresh_token_jti, principal)


@router.get("/me", response_model=UserRead)
async def me(principal: Principal = Depends(get_current_principal)):
    if not principal.user:
        return None  # type: ignore[return-value]
    return principal.user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        auth = auth_service.AuthService(session)
        await auth.change_password(
            user_id=principal.user_id,
            old_password=payload.old_password,
            new_password=payload.new_password,
        )


@router.get("/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(principal: Principal = Depends(require_user)):
    async with db_session() as session:
        return await api_key_service.ApiKeyService(session).list_for_user(
            session, principal.user_id,
        )


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        row, plain = await api_key_service.ApiKeyService(session).create(
            session, principal.user_id,
            name=payload.name,
            description=payload.description,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
        )
    return ApiKeyCreated(
        id=row.id,
        name=row.name,
        plain=plain,
        prefix=row.key_prefix,
        last4=row.key_last4,
        scopes=row.scopes,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        await api_key_service.ApiKeyService(session).revoke(
            session, principal.user_id, key_id,
        )


__all__ = ["router"]
