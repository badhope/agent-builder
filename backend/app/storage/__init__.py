"""Storage adapter package.

Re-exports the public surface: :class:`Storage` (the abstract interface)
and the two concrete adapters plus the factory.
"""

from app.storage.base import (
    ObjectMeta,
    PresignedUrl,
    Storage,
)
from app.storage.base import (
    StorageError as _StorageError,  # re-export for compatibility
)
from app.storage.factory import build_storage

__all__ = [
    "ObjectMeta",
    "PresignedUrl",
    "Storage",
    "_StorageError",
    "build_storage",
]
