"""Conversion routes: synchronously launch a single conversion."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import Principal, get_current_principal
from app.db.session import db_session
from app.schemas.task import TaskRead

router = APIRouter()


def _get_dispatcher():
    from app.services import ConverterDispatcher
    return ConverterDispatcher()


@router.post("", response_model=TaskRead, status_code=status.HTTP_202_ACCEPTED)
async def convert(
    source_file_id: uuid.UUID,
    target_format: str,
    options: dict | None = None,
    webhook_url: str | None = None,
    principal: Principal = Depends(get_current_principal),
):
    """Enqueue a conversion and return the task descriptor."""
    async with db_session() as session:
        return await _get_dispatcher().enqueue(
            session=session,
            principal=principal,
            source_file_id=str(source_file_id),
            target_format=target_format,
            options=options or {},
            webhook_url=webhook_url,
        )


@router.post("/sync", response_model=TaskRead)
async def convert_sync(
    source_file_id: uuid.UUID,
    target_format: str,
    timeout_s: int = 60,
    options: dict | None = None,
    principal: Principal = Depends(get_current_principal),
):
    """Synchronously convert a small file (blocks the worker inline)."""
    async with db_session() as session:
        return await _get_dispatcher().enqueue_sync(
            session=session,
            principal=principal,
            source_file_id=str(source_file_id),
            target_format=target_format,
            options=options or {},
            timeout_s=timeout_s,
        )


__all__ = ["router"]
