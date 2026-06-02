"""Backend adapters — one module per engine.

Each backend module exposes a small façade that performs the
engine-specific invocation. Converters consume these façades rather
than subprocess logic directly.
"""

from app.converters.backends import (
    libreoffice,
    pandoc,
    pillow,
    pillow_backend,
    tesseract,
    weasyprint,
    weasyprint_backend,
)

__all__ = [
    "libreoffice",
    "pandoc",
    "pillow",
    "pillow_backend",  # legacy alias for pillow
    "tesseract",
    "weasyprint",
    "weasyprint_backend",  # legacy alias for weasyprint
]
