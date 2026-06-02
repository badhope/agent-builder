"""Batch routes: enqueue, status, retry, cancel."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Principal, get_current_principal
from app.db.session import db_session
from app.schemas.common import Page
from app.schemas.task import BatchRead, BatchReadWithItems
from app.services.batch_service import BatchService

router = APIRouter()


@router.get("", response_model=Page[BatchRead])
async def list_batches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    state: str | None = None,
    principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = BatchService(session)
        items, total = await svc.list_for_user(
            principal.user_id, limit=limit, offset=offset, state=state,
        )
    return Page[BatchRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/{batch_id}", response_model=BatchReadWithItems)
async def get_batch(
    batch_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = BatchService(session)
        return await svc.get_for_user(principal.user_id, str(batch_id))


@router.post("/{batch_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_batch(
    batch_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = BatchService(session)
        return await svc.cancel(principal.user_id, str(batch_id))


@router.post("/{batch_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_batch(
    batch_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = BatchService(session)
        return await svc.retry(principal.user_id, str(batch_id))


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = BatchService(session)
        await svc.delete(principal.user_id, str(batch_id))


__all__ = ["router"]
