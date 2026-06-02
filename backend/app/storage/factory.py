"""Storage factory: pick the right adapter from settings."""

from __future__ import annotations

from functools import lru_cache

from app.settings import StorageBackend, get_settings
from app.storage.base import Storage


@lru_cache(maxsize=1)
def build_storage() -> Storage:
    settings = get_settings()
    if settings.storage.backend == StorageBackend.S3:
        from app.storage.s3 import S3Storage

        return S3Storage(settings.s3)
    from app.storage.local import LocalStorage

    return LocalStorage(settings.storage.local_root)


def reset_storage_cache() -> None:
    """Used by tests to force a rebuild after settings change."""
    build_storage.cache_clear()


__all__ = ["build_storage", "reset_storage_cache"]
