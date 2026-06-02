"""Format catalog + metadata extractor tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.magic_bytes import FileCategory, detect_from_bytes
from app.services.metadata_service import metadata_service
from app.services.thumbnail_service import thumbnail_service


def test_detect_pdf_magic_bytes() -> None:
    sample = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    detected = detect_from_bytes(sample, filename="doc.pdf", strict=False)
    assert detected.extension == "pdf"
    assert detected.category == FileCategory.DOCUMENT


def test_detect_png_magic_bytes() -> None:
    sample = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    detected = detect_from_bytes(sample, filename="img.png", strict=False)
    assert detected.extension == "png"
    assert detected.category == FileCategory.IMAGE


def test_detect_zip_magic_bytes() -> None:
    sample = b"PK\x03\x04hello world"
    detected = detect_from_bytes(sample, filename="a.zip", strict=False)
    assert detected.extension == "zip"
    assert detected.category == FileCategory.ARCHIVE


def test_detect_plain_text() -> None:
    sample = b"Hello, this is a plain text file. " * 5
    detected = detect_from_bytes(sample, filename="note.txt", strict=False)
    # Plain text has no magic bytes — falls back to ext-based classification
    assert detected.extension == "txt"
    assert detected.magic_verified is False


def test_metadata_text(tmp_path: Path) -> None:
    p = tmp_path / "note.txt"
    p.write_bytes(b"Line 1\nLine 2\nLine 3")
    md = _await(metadata_service.extract(p, fmt="txt"))
    # The service samples the first N bytes for the line count
    assert "line_count_sample" in md
    assert md["line_count_sample"] == 3


def test_metadata_image_png(tmp_path: Path) -> None:
    # Minimal valid PNG (1x1 transparent)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000000500010d0a2db40000000049454e44"
        "ae426082"
    )
    p = tmp_path / "pixel.png"
    p.write_bytes(png)
    md = _await(metadata_service.extract(p, fmt="png"))
    assert md["width"] == 1
    assert md["height"] == 1


def test_thumbnail_image_png(tmp_path: Path) -> None:
    """Build a 256x256 PNG via PIL so the thumbnail is meaningfully smaller."""
    import io
    from PIL import Image

    img = Image.new("RGB", (256, 256), color="red")
    p = tmp_path / "x.png"
    img.save(p, format="PNG")
    original_size = p.stat().st_size

    thumb = _await(thumbnail_service.generate(p, fmt="png", size=32))
    assert thumb is not None
    assert thumb.startswith(b"\x89PNG")
    # Smaller than original
    assert len(thumb) <= original_size


def test_thumbnail_text_to_png(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_bytes(b"Hello world, this is a text file that should render to an image.")
    thumb = _await(thumbnail_service.generate(p, fmt="txt"))
    assert thumb is not None
    # PIL output — also PNG
    assert thumb.startswith(b"\x89PNG")


def _await(coro):
    """Run a coroutine to completion synchronously (for sync test functions)."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)
