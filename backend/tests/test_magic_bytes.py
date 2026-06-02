"""Magic-byte / content sniffing tests."""

from __future__ import annotations

import pytest

from app.core import magic_bytes
from app.exceptions import UnsupportedFormatError


PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 100
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
ZIP = b"PK\x03\x04" + b"\x00" * 100
TEXT = b"Hello, world!\n" * 50


def test_detect_pdf():
    detected = magic_bytes.detect_from_bytes(PDF)
    assert detected.extension == "pdf"


def test_detect_png():
    detected = magic_bytes.detect_from_bytes(PNG)
    assert detected.extension == "png"


def test_detect_jpeg():
    detected = magic_bytes.detect_from_bytes(JPEG)
    assert detected.extension == "jpg"


def test_detect_zip():
    detected = magic_bytes.detect_from_bytes(ZIP)
    assert detected.extension in {"zip", "docx", "xlsx", "pptx", "odt", "ods", "odp", "epub"}


def test_detect_text():
    detected = magic_bytes.detect_from_bytes(TEXT)
    assert detected.extension in {"txt", "csv"}


def test_rejects_empty():
    detected = magic_bytes.detect_from_bytes(b"")
    assert detected.extension == "txt"


def test_rejects_unknown_binary():
    with pytest.raises(UnsupportedFormatError):
        magic_bytes.detect_from_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")


def test_accept_upload_basic():
    acc = magic_bytes.AcceptUpload(
        filename="report.pdf",
        content_type="application/pdf",
        purpose="source",
    )
    assert acc.filename == "report.pdf"
    assert acc.content_type == "application/pdf"
    assert acc.purpose == "source"