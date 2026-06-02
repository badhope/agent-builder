"""Abstract storage interface.

The two concrete adapters (:class:`LocalStorage` and :class:`S3Storage`)
implement the same protocol so the rest of the application can stay
backend-agnostic.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from app.exceptions import StorageError


@dataclass(frozen=True, slots=True)
class ObjectMeta:
    """Metadata for a stored object."""

    key: str
    size: int
    content_type: str | None
    last_modified: datetime | None
    etag: str | None = None
    checksum_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class PresignedUrl:
    """A short-lived URL for direct download / upload."""

    url: str
    method: str  # GET | PUT
    expires_at: datetime
    headers: dict[str, str]


class Storage(abc.ABC):
    """Backend-agnostic object storage interface."""

    backend_name: str = "abstract"

    # ---- Read ----
    @abc.abstractmethod
    async def get_bytes(self, key: str) -> bytes: ...

    @abc.abstractmethod
    async def stream(self, key: str, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]: ...

    @abc.abstractmethod
    async def stat(self, key: str) -> ObjectMeta | None: ...

    @abc.abstractmethod
    async def exists(self, key: str) -> bool: ...

    # ---- Write ----
    @abc.abstractmethod
    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta: ...

    @abc.abstractmethod
    async def put_file(
        self,
        key: str,
        source: Path | BinaryIO,
        *,
        content_type: str | None = None,
    ) -> ObjectMeta: ...

    @abc.abstractmethod
    async def delete(self, key: str) -> bool: ...

    @abc.abstractmethod
    async def delete_many(self, keys: list[str]) -> int: ...

    # ---- Listing / housekeeping ----
    @abc.abstractmethod
    async def list_keys(self, prefix: str = "", *, limit: int = 1000) -> list[str]: ...

    @abc.abstractmethod
    async def presigned_get_url(self, key: str, *, expires_s: int = 3600) -> PresignedUrl: ...

    @abc.abstractmethod
    async def healthcheck(self) -> bool: ...

    # ---- Optional helpers (have sensible default impl) ----
    def get_local_path(self, key: str) -> str:
        """Return a local filesystem path for ``key``.

        Default: raises ``NotImplementedError``. Local adapters override
        this; remote adapters can materialise to a temp file.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support direct local access."
        )


__all__ = ["ObjectMeta", "PresignedUrl", "Storage", "StorageError"]
