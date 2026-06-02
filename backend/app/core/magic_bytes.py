"""Magic-byte / file-type detection.

Two independent checks:

1. **Extension whitelist** — fast coarse filter.
2. **Magic bytes / MIME sniffing** — examines the first few KB to confirm
   the actual content matches the claimed type.

If the two disagree, the upload is rejected with ``UnsupportedFormatError``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Final

import filetype

from app.exceptions import UnsupportedFormatError
from app.logging_config import get_logger

logger = get_logger(__name__)


class FileCategory(StrEnum):
    """High-level format categories."""

    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    MARKUP = "markup"
    DATA = "data"
    IMAGE = "image"
    EBOOK = "ebook"
    ARCHIVE = "archive"
    AUDIO = "audio"
    VIDEO = "video"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DetectedFormat:
    """The result of inspecting a file's header bytes."""

    extension: str          # canonical lower-case, e.g. "pdf"
    mime: str               # e.g. "application/pdf"
    category: FileCategory
    magic_verified: bool    # True if header bytes matched


@dataclass(frozen=True, slots=True)
class AcceptUpload:
    """An incoming upload — metadata only. Used as a Pydantic-free value object."""

    filename: str
    content_type: str | None
    purpose: str = "source"


_CATEGORY_BY_EXT: Final[dict[str, FileCategory]] = {
    # documents
    "pdf": FileCategory.DOCUMENT, "doc": FileCategory.DOCUMENT, "docx": FileCategory.DOCUMENT,
    "odt": FileCategory.DOCUMENT, "rtf": FileCategory.DOCUMENT, "txt": FileCategory.DOCUMENT,
    "md": FileCategory.MARKUP, "markdown": FileCategory.MARKUP,
    # spreadsheet
    "xls": FileCategory.SPREADSHEET, "xlsx": FileCategory.SPREADSHEET,
    "ods": FileCategory.SPREADSHEET,
    # presentation
    "ppt": FileCategory.PRESENTATION, "pptx": FileCategory.PRESENTATION,
    "odp": FileCategory.PRESENTATION,
    # markup
    "html": FileCategory.MARKUP, "htm": FileCategory.MARKUP, "xhtml": FileCategory.MARKUP,
    "rst": FileCategory.MARKUP, "tex": FileCategory.MARKUP, "epub": FileCategory.EBOOK,
    # data
    "json": FileCategory.DATA, "xml": FileCategory.DATA,
    "yaml": FileCategory.DATA, "yml": FileCategory.DATA, "toml": FileCategory.DATA,
    "csv": FileCategory.DATA, "tsv": FileCategory.DATA,
    # image
    "png": FileCategory.IMAGE, "jpg": FileCategory.IMAGE, "jpeg": FileCategory.IMAGE,
    "gif": FileCategory.IMAGE, "webp": FileCategory.IMAGE, "bmp": FileCategory.IMAGE,
    "tiff": FileCategory.IMAGE, "tif": FileCategory.IMAGE, "svg": FileCategory.IMAGE,
    "heic": FileCategory.IMAGE, "heif": FileCategory.IMAGE, "avif": FileCategory.IMAGE,
    # ebook
    "mobi": FileCategory.EBOOK, "azw": FileCategory.EBOOK, "azw3": FileCategory.EBOOK,
    "fb2": FileCategory.EBOOK, "djvu": FileCategory.EBOOK,
    # archive
    "zip": FileCategory.ARCHIVE, "tar": FileCategory.ARCHIVE, "gz": FileCategory.ARCHIVE,
    "7z": FileCategory.ARCHIVE, "rar": FileCategory.ARCHIVE, "bz2": FileCategory.ARCHIVE,
    "xz": FileCategory.ARCHIVE,
    # audio
    "mp3": FileCategory.AUDIO, "wav": FileCategory.AUDIO, "flac": FileCategory.AUDIO,
    "aac": FileCategory.AUDIO, "ogg": FileCategory.AUDIO, "m4a": FileCategory.AUDIO,
    "opus": FileCategory.AUDIO,
    # video
    "mp4": FileCategory.VIDEO, "mkv": FileCategory.VIDEO, "webm": FileCategory.VIDEO,
    "mov": FileCategory.VIDEO, "avi": FileCategory.VIDEO, "wmv": FileCategory.VIDEO,
    "flv": FileCategory.VIDEO,
}

_TEXT_EXTENSIONS: Final[set[str]] = {
    "txt", "md", "markdown", "html", "htm", "xhtml", "rst", "tex",
    "csv", "tsv", "json", "xml", "yaml", "yml", "toml",
}


# ---- Detection --------------------------------------------------------------


def detect_from_bytes(
    head: bytes,
    *,
    filename: str | None = None,
    strict: bool = True,
) -> DetectedFormat:
    """Identify the format from the first KB of the file."""
    ext_from_name = _ext_from_filename(filename) if filename else None

    kind = filetype.guess(head)
    if kind is not None:
        detected = DetectedFormat(
            extension=kind.extension,
            mime=kind.mime,
            category=_CATEGORY_BY_EXT.get(kind.extension, FileCategory.UNKNOWN),
            magic_verified=True,
        )
    else:
        detected = _guess_text_format(head, ext_from_name)

    if strict and ext_from_name and detected.magic_verified and detected.extension != ext_from_name:
        logger.warning(
            "magic.extension_mismatch",
            filename=filename,
            claimed=ext_from_name,
            detected=detected.extension,
        )
        raise UnsupportedFormatError(
            "File extension does not match file content.",
            code="EXTENSION_CONTENT_MISMATCH",
            details={"claimed": ext_from_name, "detected": detected.extension},
        )

    if not detected.magic_verified and ext_from_name:
        detected = DetectedFormat(
            extension=ext_from_name,
            mime="application/octet-stream",
            category=_CATEGORY_BY_EXT.get(ext_from_name, FileCategory.UNKNOWN),
            magic_verified=False,
        )

    if detected.category == FileCategory.UNKNOWN and strict:
        raise UnsupportedFormatError(
            "Could not determine the file format.",
            code="UNKNOWN_FORMAT",
            details={"filename": filename},
        )

    return detected


def is_text_format(ext: str) -> bool:
    return ext.lower() in _TEXT_EXTENSIONS


def compute_sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def sha256_stream(chunks: list[bytes]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c)
    return h.hexdigest()


def _ext_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    suffix = PurePosixPath(filename).suffix
    if not suffix:
        return None
    return suffix.lstrip(".").lower()


def _guess_text_format(head: bytes, fallback_ext: str | None) -> DetectedFormat:
    sample = head[:4096]
    if sample.startswith(b"\xef\xbb\xbf"):
        sample = sample[3:]
    if sample.startswith(b"\xfe\xff") or sample.startswith(b"\xff\xfe"):
        return DetectedFormat(
            extension="txt", mime="text/plain", category=FileCategory.DOCUMENT, magic_verified=False,
        )

    try:
        text = sample.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return DetectedFormat(
            extension=fallback_ext or "bin",
            mime="application/octet-stream",
            category=FileCategory.UNKNOWN,
            magic_verified=False,
        )

    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return DetectedFormat(
            extension="json", mime="application/json", category=FileCategory.DATA, magic_verified=False,
        )
    if stripped.startswith("<?xml") or stripped.startswith("<"):
        return DetectedFormat(
            extension="xml", mime="application/xml", category=FileCategory.DATA, magic_verified=False,
        )
    if stripped.startswith("# ") or stripped.startswith("## ") or "\n#" in stripped[:500]:
        return DetectedFormat(
            extension="md", mime="text/markdown", category=FileCategory.MARKUP, magic_verified=False,
        )
    if "\t" in text[:1024] and "," not in text[:1024]:
        return DetectedFormat(
            extension="tsv", mime="text/tab-separated-values", category=FileCategory.DATA, magic_verified=False,
        )
    if "," in text[:1024]:
        return DetectedFormat(
            extension="csv", mime="text/csv", category=FileCategory.DATA, magic_verified=False,
        )
    return DetectedFormat(
        extension=fallback_ext or "txt",
        mime="text/plain",
        category=FileCategory.DOCUMENT,
        magic_verified=False,
    )


__all__ = [
    "AcceptUpload",
    "DetectedFormat",
    "FileCategory",
    "compute_sha256",
    "detect_from_bytes",
    "is_text_format",
    "sha256_stream",
]
