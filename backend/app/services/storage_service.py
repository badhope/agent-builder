"""Storage service — high-level helpers built on top of the ``Storage`` adapter.

The service is responsible for:

* computing per-user/per-task object keys
* storing an upload as bytes and persisting a ``File`` row
* streaming objects back (with or without ownership checks)
* anti-virus scanning (best effort, configurable)
* signing short-lived download tokens
* enumerating, deleting, restoring, and soft-deleting ``File`` rows
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import aiofiles.os
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.antivirus import antivirus_scanner
from app.core.magic_bytes import AcceptUpload, detect_from_bytes
from app.core.sanitizers import sanitize_filename
from app.db.models.file import File, FilePurpose, FileScanStatus
from app.db.models.user import User
from app.exceptions import (
    AuthorizationError,
    FileTooLargeError,
    NotFoundError,
    UnsupportedFormatError,
)
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.api.deps import Principal
from app.settings import get_settings
from app.storage.base import ObjectMeta, Storage
from app.storage.factory import build_storage

logger = get_logger(__name__)


class StorageService:
    """Convenience facade over the configured ``Storage`` backend + DB."""

    def __init__(self, storage: Storage | None = None) -> None:
        self._storage = storage or build_storage()

    # ------------------------------------------------------------------
    # Properties / factory helpers
    # ------------------------------------------------------------------

    @property
    def backend(self) -> Storage:
        return self._storage

    @property
    def backend_name(self) -> str:
        return self._storage.backend_name

    # ------------------------------------------------------------------
    # Key builders
    # ------------------------------------------------------------------

    def user_key(self, user_id: uuid.UUID, *parts: str) -> str:
        safe = [sanitize_filename(p, fallback="file") for p in parts if p]
        return f"users/{user_id}/" + "/".join(safe) if safe else f"users/{user_id}"

    def task_key(self, user_id: uuid.UUID, task_id: uuid.UUID, *parts: str) -> str:
        safe = [sanitize_filename(p, fallback="file") for p in parts if p]
        return f"users/{user_id}/tasks/{task_id}/" + "/".join(safe) if safe else f"users/{user_id}/tasks/{task_id}"

    def batch_key(self, user_id: uuid.UUID, batch_id: uuid.UUID, *parts: str) -> str:
        safe = [sanitize_filename(p, fallback="file") for p in parts if p]
        return f"users/{user_id}/batches/{batch_id}/" + "/".join(safe) if safe else f"users/{user_id}/batches/{batch_id}"

    # ------------------------------------------------------------------
    # Low-level put / get / stream
    # ------------------------------------------------------------------

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta:
        return await self._storage.put_bytes(key, data, content_type=content_type)

    async def put_file(
        self,
        key: str,
        source: Path,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta:
        return await self._storage.put_file(key, source, content_type=content_type)

    async def get_bytes(self, key: str) -> bytes:
        return await self._storage.get_bytes(key)

    async def get_file_bytes(self, file: File) -> bytes:
        return await self._storage.get_bytes(file.storage_key)

    async def stream(
        self, key: str, chunk_size: int = 64 * 1024,
    ) -> AsyncIterator[bytes]:
        async for chunk in self._storage.stream(key, chunk_size=chunk_size):
            yield chunk

    async def stream_to_file(self, key: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            async with aiofiles.open(tmp, "wb") as f:
                async for chunk in self._storage.stream(key):
                    await f.write(chunk)
            tmp.replace(dest)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise

    async def delete(self, key: str) -> bool:
        return await self._storage.delete(key)

    async def delete_many(self, keys: list[str]) -> int:
        return await self._storage.delete_many(keys)

    async def stat(self, key: str) -> ObjectMeta | None:
        return await self._storage.stat(key)

    async def healthcheck(self) -> bool:
        return await self._storage.healthcheck()

    # ------------------------------------------------------------------
    # High-level: store_bytes() for direct uploads
    # ------------------------------------------------------------------

    async def store_bytes(
        self,
        session: AsyncSession,
        principal: Principal,
        data: bytes,
        accept: AcceptUpload,
        *,
        source: str = "direct_upload",
    ) -> File:
        """Persist a new ``File`` row for ``principal``.

        Performs:

        1. size cap enforcement (per user, per global)
        2. magic-byte sniffing (strict — extension must match content)
        3. SHA-256 hash
        4. upload to the storage backend
        5. anti-virus scan (if enabled) — marks the row accordingly
        6. returns the persisted ``File``
        """
        if not principal.user_id:
            raise AuthorizationError("Authentication required.")
        if not data:
            raise UnsupportedFormatError("Empty payload.", code="EMPTY_PAYLOAD")

        settings = get_settings()
        user: User = principal.user  # type: ignore[assignment]
        if not user.is_active:
            raise AuthorizationError("User is inactive.", code="USER_INACTIVE")

        max_bytes = user.quota_max_file_size_mb * 1024 * 1024
        global_max = settings.conversion.file_size_bytes
        cap = min(max_bytes, global_max) if max_bytes else global_max
        if len(data) > cap:
            raise FileTooLargeError(
                "File exceeds maximum size.",
                details={
                    "max_bytes": cap,
                    "filename": accept.filename,
                    "user_max_mb": user.quota_max_file_size_mb,
                },
            )

        # Magic-byte detection
        detected = detect_from_bytes(
            data[:4096], filename=accept.filename, strict=True,
        )

        # Compute hash
        sha = hashlib.sha256(data).hexdigest()

        # Build key
        safe_name = sanitize_filename(accept.filename, fallback="upload")
        file_id = uuid.uuid4()
        purpose_value = (
            accept.purpose if accept.purpose in {p.value for p in FilePurpose}
            else FilePurpose.SOURCE.value
        )
        key = self.user_key(user.id, file_id.hex, safe_name)

        # Upload
        await self._storage.put_bytes(
            key, data, content_type=detected.mime or accept.content_type,
        )

        # Anti-virus scan (best effort)
        scan = await antivirus_scanner.scan_bytes_async(data)

        file = File(
            id=file_id,
            owner_id=user.id,
            storage_backend=self._storage.backend_name,
            storage_key=key,
            purpose=FilePurpose(purpose_value),
            filename=safe_name,
            content_type=detected.mime or accept.content_type,
            size=len(data),
            sha256=sha,
            format=detected.extension,
            scan_status=(
                FileScanStatus.CLEAN
                if scan.clean
                else (FileScanStatus.INFECTED if scan.signature else FileScanStatus.ERROR)
            ),
            scan_signature=scan.signature,
            scan_at=datetime.now(tz=UTC),
            scan_engine=scan.engine,
            metadata_json={
                "source": source,
                "category": detected.category.value,
                "magic_verified": detected.magic_verified,
            },
            expires_at=datetime.now(tz=UTC) + timedelta(hours=24),
        )

        if not scan.clean and scan.signature:
            # Infected — delete from storage, raise
            from app.exceptions import AntivirusError
            await self._storage.delete(key)
            raise AntivirusError(
                f"File rejected by anti-virus: {scan.signature}",
                code="ANTIVIRUS_REJECTED",
                details={"signature": scan.signature, "engine": scan.engine},
            )

        session.add(file)
        await session.flush()
        return file

    # ------------------------------------------------------------------
    # Listing / fetching
    # ------------------------------------------------------------------

    async def list_files(
        self,
        session: AsyncSession,
        principal: Principal,
        *,
        limit: int = 50,
        offset: int = 0,
        purpose: str | None = None,
    ) -> tuple[list[File], int]:
        if not principal.user_id:
            raise AuthorizationError("Authentication required.")
        stmt = (
            select(File)
            .where(File.owner_id == principal.user_id, File.deleted_at.is_(None))
            .order_by(desc(File.created_at))
            .limit(limit)
            .offset(offset)
        )
        if purpose is not None:
            stmt = stmt.where(File.purpose == FilePurpose(purpose))
        rows = list((await session.execute(stmt)).scalars().all())
        count_stmt = (
            select(func.count())
            .select_from(File)
            .where(File.owner_id == principal.user_id, File.deleted_at.is_(None))
        )
        if purpose is not None:
            count_stmt = count_stmt.where(File.purpose == FilePurpose(purpose))
        total = int((await session.execute(count_stmt)).scalar_one())
        return rows, total

    async def get_file(
        self,
        session: AsyncSession,
        principal: Principal,
        file_id: str,
    ) -> File | None:
        if not principal.user_id:
            raise AuthorizationError("Authentication required.")
        try:
            fid = uuid.UUID(file_id)
        except ValueError as exc:
            raise NotFoundError("Invalid file id.", code="FILE_NOT_FOUND") from exc
        file = await session.get(File, fid)
        if file is None or file.deleted_at is not None:
            return None
        if file.owner_id != principal.user_id and not (
            principal.is_admin and file.purpose != FilePurpose.AVATAR
        ):
            raise AuthorizationError("You do not have access to this file.", code="FILE_FORBIDDEN")
        return file

    async def stream_file(
        self,
        session: AsyncSession,
        principal: Principal,
        file_id: str,
    ) -> tuple[File, AsyncIterator[bytes]]:
        file = await self.get_file(session, principal, file_id)
        if file is None:
            raise NotFoundError("File not found.", code="FILE_NOT_FOUND")
        # Increment download counter
        await session.execute(
            update(File)
            .where(File.id == file.id)
            .values(
                download_count=File.download_count + 1,
                last_downloaded_at=datetime.now(tz=UTC),
            )
        )
        await session.flush()
        return file, self.stream(file.storage_key)

    async def stream_file_ownerless(
        self,
        session: AsyncSession,
        file_id: str,
    ) -> tuple[File, AsyncIterator[bytes]]:
        try:
            fid = uuid.UUID(file_id)
        except ValueError as exc:
            raise NotFoundError("Invalid file id.", code="FILE_NOT_FOUND") from exc
        file = await session.get(File, fid)
        if file is None or file.deleted_at is not None:
            raise NotFoundError("File not found.", code="FILE_NOT_FOUND")
        await session.execute(
            update(File)
            .where(File.id == file.id)
            .values(
                download_count=File.download_count + 1,
                last_downloaded_at=datetime.now(tz=UTC),
            )
        )
        await session.flush()
        return file, self.stream(file.storage_key)

    # ------------------------------------------------------------------
    # Delete / restore
    # ------------------------------------------------------------------

    async def delete_file(
        self,
        session: AsyncSession,
        principal: Principal,
        file_id: str,
        *,
        hard: bool = False,
    ) -> None:
        file = await self.get_file(session, principal, file_id)
        if file is None:
            raise NotFoundError("File not found.", code="FILE_NOT_FOUND")
        if hard:
            await self._storage.delete(file.storage_key)
            await session.delete(file)
        else:
            file.deleted_at = datetime.now(tz=UTC)
            file.deleted_reason = "user_requested"
            await session.flush()

    async def restore_file(
        self,
        session: AsyncSession,
        principal: Principal,
        file_id: str,
    ) -> File:
        file = await self.get_file(session, principal, file_id)
        if file is None or file.deleted_at is None:
            raise NotFoundError("File not found or not deleted.", code="FILE_NOT_FOUND")
        file.deleted_at = None
        file.deleted_reason = None
        await session.flush()
        return file

    # ------------------------------------------------------------------
    # Signed download URL helpers
    # ------------------------------------------------------------------

    def default_ttl(self) -> timedelta:
        return timedelta(hours=24)

    def build_storage_key_for_upload(
        self, user: User, file_id: uuid.UUID, filename: str,
    ) -> str:
        return self.user_key(user.id, file_id.hex, filename)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def storage_used_for_user(
        self, session: AsyncSession, user_id: uuid.UUID,
    ) -> int:
        stmt = select(func.coalesce(func.sum(File.size), 0)).where(
            File.owner_id == user_id,
            File.deleted_at.is_(None),
        )
        return int((await session.execute(stmt)).scalar_one())


__all__ = ["StorageService"]
