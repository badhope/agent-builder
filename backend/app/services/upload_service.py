"""Backward-compat shim — the actual upload logic lives in
:mod:`app.services.storage_service` (see :meth:`StorageService.store_bytes`).
This module is kept so older imports keep working.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.magic_bytes import AcceptUpload, detect_from_bytes  # noqa: F401

__all__ = ["AcceptUpload", "AcceptedUpload", "UploadService"]


@dataclass(slots=True, frozen=True)
class AcceptedUpload:
    """The result of accepting an upload (legacy name)."""

    storage_key: str
    file_name: str
    size: int
    format: str
    mime: str
    sha256: str


class UploadService:
    """Deprecated thin wrapper. Use :class:`app.services.storage_service.StorageService`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "UploadService has been replaced by StorageService.store_bytes()."
        )
