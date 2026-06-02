"""Download service — short-lived signed tokens for ownerless streaming.

Flow:

* :meth:`issue_download_token` returns an HMAC-signed token bound to a
  single ``file_id`` and an optional ``user_id``.
* :meth:`verify_download_token` decodes the token, checks the file_id
  matches, and confirms the signature is valid and unexpired.
* :meth:`stream_signed` is a convenience wrapper that streams a ``File``
  row's content from the storage backend (no DB access required after
  the token is verified).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SignedTokenIssuer
from app.db.models.file import File
from app.exceptions import AuthenticationError, NotFoundError
from app.services.storage_service import StorageService


class DownloadService:
    """Streams files from storage after verifying the caller's token."""

    def __init__(self, db: AsyncSession, storage: StorageService | None = None) -> None:
        self.db = db
        self.storage = storage or StorageService()
        self._issuer = SignedTokenIssuer()

    # ---- token helpers ----

    def issue_download_token(
        self,
        file_id: uuid.UUID | str,
        user_id: uuid.UUID | str | None = None,
        *,
        expires_in: int = 3600,
    ) -> str:
        try:
            fid = file_id if isinstance(file_id, uuid.UUID) else uuid.UUID(str(file_id))
        except (ValueError, TypeError) as exc:
            raise NotFoundError("Invalid file id.", code="FILE_NOT_FOUND") from exc
        return self._issuer.issue(
            subject=str(fid),
            extra={"user_id": str(user_id) if user_id else None},
            ttl_s=expires_in,
        )

    def verify_download_token(
        self,
        token: str,
        file_id: uuid.UUID | str,
    ) -> dict[str, Any]:
        try:
            fid = file_id if isinstance(file_id, uuid.UUID) else uuid.UUID(str(file_id))
        except (ValueError, TypeError) as exc:
            raise AuthenticationError("Invalid file id.", code="BAD_FILE_ID") from exc
        try:
            payload = self._issuer.verify(token)
        except AuthenticationError:
            raise
        if payload.get("sub") != str(fid):
            raise AuthenticationError(
                "Token does not match the requested file.", code="TOKEN_FILE_MISMATCH",
            )
        return payload

    # ---- streaming ----

    async def stream(
        self, file: File,
    ) -> AsyncIterator[bytes]:
        async for chunk in self.storage.stream(file.storage_key):
            yield chunk

    async def record_download(
        self, file: File, *, ip: str | None = None,
    ) -> None:
        await self.db.execute(
            update(File)
            .where(File.id == file.id)
            .values(
                download_count=File.download_count + 1,
                last_downloaded_at=datetime.now(tz=UTC),
                last_download_ip=ip,
            )
        )

    async def resolve_for_download(
        self, file_id: uuid.UUID | str, user_id: uuid.UUID | str | None = None,
    ) -> File:
        try:
            fid = file_id if isinstance(file_id, uuid.UUID) else uuid.UUID(str(file_id))
        except (ValueError, TypeError) as exc:
            raise NotFoundError("File not found.", code="FILE_NOT_FOUND") from exc
        file = await self.db.get(File, fid)
        if file is None or file.deleted_at is not None:
            raise NotFoundError("File not found.", code="FILE_NOT_FOUND")
        if user_id is not None and file.owner_id != uuid.UUID(str(user_id)):
            raise AuthenticationError(
                "You do not have access to this file.", code="FILE_FORBIDDEN",
            )
        return file


__all__ = ["DownloadService"]
