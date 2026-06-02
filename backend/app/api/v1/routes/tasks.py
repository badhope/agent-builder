"""Task routes: list, fetch, retry, cancel, delete, logs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Principal, get_current_principal, require_user
from app.db.session import db_session
from app.schemas.common import Page
from app.schemas.task import TaskLogRead, TaskRead
from app.services.task_service import TaskService

router = APIRouter()


@router.get("", response_model=Page[TaskRead])
async def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    state: str | None = None,
    source_format: str | None = None,
    target_format: str | None = None,
    principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        svc = TaskService(session)
        items, total = await svc.list_for_user(
            principal.user_id,
            limit=limit,
            offset=offset,
            state=state,
            source_format=source_format,
            target_format=target_format,
        )
    return Page[TaskRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = TaskService(session)
        return await svc.get_for_user(principal.user_id, str(task_id))


@router.get("/{task_id}/logs", response_model=list[TaskLogRead])
async def get_task_logs(
    task_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = TaskService(session)
        return await svc.logs_for_user(principal.user_id, str(task_id))


@router.post("/{task_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(
    task_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = TaskService(session)
        return await svc.cancel(principal.user_id, str(task_id))


@router.post("/{task_id}/retry", response_model=TaskRead, status_code=status.HTTP_202_ACCEPTED)
async def retry_task(
    task_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = TaskService(session)
        return await svc.retry(principal.user_id, str(task_id))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        svc = TaskService(session)
        await svc.delete(principal.user_id, str(task_id))


__all__ = ["router"]
