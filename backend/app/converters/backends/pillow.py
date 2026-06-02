"""Pillow (PIL) façade for image format conversions (canonical location).

The legacy ``pillow_backend`` import path is preserved as a shim for
backwards compatibility — see ``pillow_backend.py``.
"""

from __future__ import annotations

import functools
from pathlib import Path

from PIL import Image

# SECURITY: Allow-list of Pillow save formats. Pillow's ``save()`` method
# accepts arbitrary format strings and looks up parsers by name. Some of
# those parsers have a history of memory-safety and DoS bugs (e.g.
# CVE-2023-44271 in the past), so we restrict to a small, well-tested
# set. Requests for any other format must be rejected here rather than
# passed through to ``img.save()``.
_ALLOWED_FORMATS: frozenset[str] = frozenset(
    {"PNG", "JPEG", "JPG", "WEBP", "TIFF", "BMP", "GIF", "PPM", "ICO", "TGA"},
)


@functools.lru_cache(maxsize=1)
def is_available() -> bool:
    """Whether Pillow is importable. Cached per process."""
    try:
        Image.new("RGB", (1, 1))
        return True
    except Exception:
        return False


def normalize_target_format(target_format: str) -> str:
    """Return the canonical uppercase format string or raise ``ValueError``."""
    fmt = target_format.upper().lstrip(".")
    if fmt not in _ALLOWED_FORMATS:
        raise ValueError(
            f"Unsupported image target format: {target_format!r}. "
            f"Allowed: {sorted(_ALLOWED_FORMATS)}"
        )
    return fmt


def convert_image(
    input_path: Path,
    output_path: Path,
    *,
    target_format: str,
    quality: int = 90,
    optimize: bool = True,
) -> None:
    """Convert an image to ``target_format``.

    ``target_format`` is the Pillow format name, e.g. ``"PNG"``, ``"JPEG"``,
    ``"WEBP"``, ``"TIFF"``, ``"BMP"``. The format is validated against
    :data:`_ALLOWED_FORMATS` before being passed to Pillow.
    """
    fmt = normalize_target_format(target_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as img:
        # Mode fix-up: JPEG can't have alpha
        if fmt in {"JPEG", "JPG"} and img.mode in {"RGBA", "P", "LA"}:
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode in {"RGBA", "LA"}:
                background.paste(img, mask=img.split()[-1])
            else:  # P
                background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            img = background
        elif fmt == "PNG" and img.mode == "P":
            img = img.convert("RGBA")
        save_kwargs: dict = {}
        if fmt in {"JPEG", "JPG", "WEBP"}:
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = optimize
        img.save(output_path, format=fmt, **save_kwargs)


__all__ = ["convert_image", "is_available", "normalize_target_format"]
