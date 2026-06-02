"""Backwards-compatibility shim for the legacy ``pillow_backend`` import path.

This module re-exports the canonical :mod:`app.converters.backends.pillow`
so that older code importing ``from app.converters.backends import pillow_backend``
continues to work. New code should import :mod:`pillow` directly.
"""

from app.converters.backends.pillow import (
    convert_image,
    is_available,
    normalize_target_format,
)

__all__ = ["convert_image", "is_available", "normalize_target_format"]
