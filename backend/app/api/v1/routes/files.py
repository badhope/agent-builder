"""File routes: direct upload, list, delete, download, signed download."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import Principal, get_current_principal
from app.db.session import db_session
from app.exceptions import FileTooLargeError, NotFoundError
from app.schemas.common import Page
from app.schemas.file import FileRead
from app.services import download_service, storage_service
from app.services.upload_service import AcceptUpload
from app.settings import get_settings

router = APIRouter()


@router.post("/uploads", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def direct_upload(
    file: UploadFile,
    purpose: str = Query("source", pattern="^(source|asset|avatar)$"),
    principal: Principal = Depends(get_current_principal),
):
    settings = get_settings()
    max_bytes = settings.conversion.file_size_bytes
    acc = AcceptUpload(
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        purpose=purpose,
    )
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1 << 20)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(f"File exceeds maximum size of {max_bytes} bytes")
        chunks.append(chunk)
    data = b"".join(chunks)
    async with db_session() as session:
        stored = await storage_service.store_bytes(
            session, principal, data, acc, source="direct_upload",
        )
    return stored


@router.get("", response_model=Page[FileRead])
async def list_files(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    purpose: str | None = None,
    principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        items, total = await storage_service.list_files(
            session, principal, limit=limit, offset=offset, purpose=purpose,
        )
    return Page[FileRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/{file_id}", response_model=FileRead)
async def get_file(file_id: uuid.UUID, principal: Principal = Depends(get_current_principal)):
    async with db_session() as session:
        f = await storage_service.get_file(session, principal, str(file_id))
        if f is None:
            raise NotFoundError(f"File {file_id} not found")
        return f


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        meta, stream = await storage_service.stream_file(session, principal, str(file_id))
    if stream is None:
        raise NotFoundError(f"File {file_id} not found")
    return StreamingResponse(
        stream,
        media_type=meta.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{meta.filename}"',
            "Content-Length": str(meta.size),
        },
    )


@router.get("/{file_id}/signed-url")
async def signed_download(
    file_id: uuid.UUID,
    expires_in: int = Query(3600, ge=60, le=86400),
    principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        meta = await storage_service.get_file(session, principal, str(file_id))
    if meta is None:
        raise NotFoundError(f"File {file_id} not found")
    token = download_service.issue_download_token(str(file_id), expires_in=expires_in)
    return {"url": f"/v1/files/{file_id}/stream?token={token}", "expires_in": expires_in}


@router.get("/{file_id}/stream")
async def stream_with_token(file_id: uuid.UUID, token: str):
    from app.services.storage_service import StorageService
    download_service.verify_download_token(token, str(file_id))
    # Ownerless stream once a signed token is presented
    async with db_session() as session:
        svc = StorageService()
        meta, stream = await svc.stream_file_ownerless(session, str(file_id))
    if stream is None:
        raise NotFoundError(f"File {file_id} not found")
    return StreamingResponse(
        stream,
        media_type=meta.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{meta.filename}"'},
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID, principal: Principal = Depends(get_current_principal),
):
    async with db_session() as session:
        await storage_service.delete_file(session, principal, str(file_id))


__all__ = ["router"]
