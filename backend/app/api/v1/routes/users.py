"""User management routes (self-service + admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import Principal, get_current_principal, require_admin
from app.db.session import db_session
from app.schemas.user import UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_me(principal: Principal = Depends(get_current_principal)):
    async with db_session() as session:
        svc = UserService(session)
        return await svc.get_by_id(principal.user_id)


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = UserService(session)
        return await svc.update_profile(
            principal.user_id,
            full_name=payload.full_name,
            avatar_url=payload.avatar_url,
        )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(principal: Principal = Depends(get_current_principal)):
    async with db_session() as session:
        svc = UserService(session)
        await svc.deactivate(principal.user_id)


# ---- Admin-only ----

@router.get("", response_model=list[UserRead], dependencies=[Depends(require_admin)])
async def list_users(
    limit: int = 50, offset: int = 0, q: str | None = None,
):
    async with db_session() as session:
        svc = UserService(session)
        return await svc.list(limit=limit, offset=offset, query=q)


@router.get("/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
async def get_user(user_id: str):
    async with db_session() as session:
        svc = UserService(session)
        user = await svc.get_by_id(user_id)
        if user is None:
            from app.exceptions import NotFoundError
            raise NotFoundError(f"User {user_id} not found")
        return user


@router.patch("/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
async def admin_update_user(user_id: str, payload: UserUpdate):
    async with db_session() as session:
        svc = UserService(session)
        return await svc.admin_update(user_id, payload)


@router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def admin_delete_user(user_id: str):
    async with db_session() as session:
        svc = UserService(session)
        await svc.admin_delete(user_id)


__all__ = ["router"]
