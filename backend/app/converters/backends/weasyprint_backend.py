"""Backwards-compatibility shim for the legacy ``weasyprint_backend`` import path.

This module re-exports the canonical :mod:`app.converters.backends.weasyprint`
so that older code importing ``from app.converters.backends import weasyprint_backend``
continues to work. New code should import :mod:`weasyprint` directly.
"""

from app.converters.backends.weasyprint import html_to_pdf, is_available

__all__ = ["html_to_pdf", "is_available"]
