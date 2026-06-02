"""Local filesystem storage adapter.

Files are stored under ``STORAGE_LOCAL_ROOT``. Keys are POSIX-style
relative paths; the adapter rejects any key that contains traversal
sequences (``..``, absolute paths).
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

import aiofiles
import aiofiles.os

from app.core.sanitizers import safe_join
from app.exceptions import StorageError
from app.logging_config import get_logger
from app.storage.base import ObjectMeta, PresignedUrl, Storage

logger = get_logger(__name__)


class LocalStorage(Storage):
    backend_name = "local"

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        # Make root readable only by current user
        try:
            os.chmod(self.root, 0o750)
        except PermissionError:  # pragma: no cover
            pass

    # ---- Internal helpers ----

    def _resolve(self, key: str) -> Path:
        if not key or key.startswith("/"):
            raise StorageError("Invalid storage key.", code="INVALID_KEY")
        parts = key.split("/")
        # safe_join validates against path traversal
        return safe_join(self.root, *parts)

    # ---- Read ----

    async def get_bytes(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists() or not path.is_file():
            raise StorageError(f"Object not found: {key}", code="OBJECT_NOT_FOUND")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def stream(self, key: str, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        path = self._resolve(key)
        if not path.exists() or not path.is_file():
            raise StorageError(f"Object not found: {key}", code="OBJECT_NOT_FOUND")
        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def stat(self, key: str) -> ObjectMeta | None:
        path = self._resolve(key)
        try:
            st = await aiofiles.os.stat(path)
        except FileNotFoundError:
            return None
        return ObjectMeta(
            key=key,
            size=st.st_size,
            content_type=_guess_mime(path),
            last_modified=datetime.fromtimestamp(st.st_mtime, tz=UTC),
            etag=None,
            checksum_sha256=None,
        )

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return await aiofiles.os.path.exists(path)

    # ---- Write ----

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            async with aiofiles.open(tmp, "wb") as f:
                await f.write(data)
            await asyncio.to_thread(os.replace, tmp, path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        return ObjectMeta(
            key=key,
            size=len(data),
            content_type=content_type or _guess_mime(path),
            last_modified=datetime.now(tz=UTC),
            etag=None,
            checksum_sha256=hashlib.sha256(data).hexdigest(),
        )

    async def put_file(
        self,
        key: str,
        source: Path | BinaryIO,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256()

        if isinstance(source, Path):
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            try:
                with open(source, "rb") as src, open(tmp, "wb") as dst:
                    while True:
                        chunk = src.read(64 * 1024)
                        if not chunk:
                            break
                        sha.update(chunk)
                        dst.write(chunk)
                os.replace(tmp, path)
            except Exception:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
                raise
        else:
            tmp = path.with_suffix(path.suffix + ".tmp")
            try:
                with open(tmp, "wb") as dst:
                    while True:
                        chunk = source.read(64 * 1024)
                        if not chunk:
                            break
                        sha.update(chunk)
                        dst.write(chunk)
                os.replace(tmp, path)
            except Exception:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
                raise

        size = path.stat().st_size
        return ObjectMeta(
            key=key,
            size=size,
            content_type=content_type or _guess_mime(path),
            last_modified=datetime.now(tz=UTC),
            etag=None,
            checksum_sha256=sha.hexdigest(),
        )

    async def delete(self, key: str) -> bool:
        path = self._resolve(key)
        if not path.exists():
            return False
        await asyncio.to_thread(path.unlink)
        return True

    async def delete_many(self, keys: list[str]) -> int:
        deleted = 0
        for k in keys:
            if await self.delete(k):
                deleted += 1
        return deleted

    # ---- Listing ----

    async def list_keys(self, prefix: str = "", *, limit: int = 1000) -> list[str]:
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        base = self._resolve(prefix) if prefix else self.root
        if not base.exists():
            return []
        keys: list[str] = []
        for root_dir, _dirs, files in os.walk(base):
            for fname in files:
                full = Path(root_dir) / fname
                try:
                    rel = full.relative_to(self.root).as_posix()
                except ValueError:
                    continue
                keys.append(rel)
                if len(keys) >= limit:
                    return keys
        return keys

    async def presigned_get_url(self, key: str, *, expires_s: int = 3600) -> PresignedUrl:
        # Local FS has no real presigning; produce a signed token path.
        # The HTTP layer will translate this to ``/v1/files/{id}/download?token=...``

        # Caller is expected to know the file_id; here we just provide
        # an opaque URL with an embedded token. The streaming endpoint
        # is in /v1/files/{file_id}/download.
        raise NotImplementedError(
            "Use /v1/files/{id}/download with a SignedTokenIssuer token."
        )

    async def healthcheck(self) -> bool:
        try:
            return self.root.exists() and os.access(self.root, os.W_OK)
        except OSError:
            return False

    def get_local_path(self, key: str) -> str:
        return str(self._resolve(key))


def _guess_mime(path: Path) -> str | None:
    mime, _ = mimetypes.guess_type(path.name)
    return mime


__all__ = ["LocalStorage"]
