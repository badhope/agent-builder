"""Format-specific metadata extraction.

The extractor is a thin façade that returns a JSON-safe ``dict`` of
metadata for a stored object. Implementations are deliberately small and
tolerant — a missing dependency is logged, never raised into the request.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from app.core.magic_bytes import is_text_format
from app.logging_config import get_logger

logger = get_logger(__name__)


class MetadataService:
    """Extract metadata for a file on disk."""

    async def extract(self, file_path: Path, fmt: str | None) -> dict[str, Any]:
        if not file_path.exists():
            return {}
        fmt_l = (fmt or "").lower()
        if fmt_l == "pdf":
            return self._pdf_metadata(file_path)
        if fmt_l in {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "tif"}:
            return self._image_metadata(file_path)
        if fmt_l in {"mp4", "mov", "mkv", "webm", "avi", "flv", "wmv"}:
            return self._video_metadata(file_path)
        if fmt_l in {"mp3", "wav", "flac", "aac", "ogg", "m4a", "opus"}:
            return self._audio_metadata(file_path)
        if is_text_format(fmt_l):
            return self._text_metadata(file_path)
        return self._generic_metadata(file_path)

    # ---- helpers ----

    def _generic_metadata(self, p: Path) -> dict[str, Any]:
        try:
            stat = p.stat()
            return {
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        except OSError:
            return {}

    def _text_metadata(self, p: Path) -> dict[str, Any]:
        out = self._generic_metadata(p)
        try:
            with p.open("rb") as f:
                data = f.read(64 * 1024)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("utf-8", errors="replace")
            out["encoding"] = "utf-8"
            out["line_count_sample"] = text.count("\n") + 1
            out["char_count_sample"] = len(text)
            if text.startswith("{") or text.startswith("["):
                try:
                    json.loads(text)
                    out["json_valid"] = True
                except json.JSONDecodeError:
                    out["json_valid"] = False
        except OSError:
            pass
        return out

    def _image_metadata(self, p: Path) -> dict[str, Any]:
        out = self._generic_metadata(p)
        try:
            from PIL import Image
            with Image.open(p) as im:
                out["width"] = im.width
                out["height"] = im.height
                out["mode"] = im.mode
                if im.format:
                    out["format"] = im.format
                if hasattr(im, "info"):
                    out["info"] = {k: str(v)[:120] for k, v in im.info.items()}
        except Exception as exc:
            logger.debug("metadata.image_failed", error=str(exc))
        return out

    def _pdf_metadata(self, p: Path) -> dict[str, Any]:
        out = self._generic_metadata(p)
        try:
            import pypdf
            with pypdf.PdfReader(str(p)) as reader:
                out["page_count"] = len(reader.pages)
                md = reader.metadata
                if md:
                    out["pdf_metadata"] = {
                        k.lstrip("/"): str(v)[:200]
                        for k, v in md.items()
                    }
        except Exception as exc:
            logger.debug("metadata.pdf_failed", error=str(exc))
            # Fallback to raw parse for /Count
            try:
                with p.open("rb") as f:
                    head = f.read(8 * 1024 * 1024)
                if head.startswith(b"%PDF"):
                    out["page_count"] = head.count(b"/Type /Page") + head.count(b"/Type/Page")
            except OSError:
                pass
        return out

    def _audio_metadata(self, p: Path) -> dict[str, Any]:
        out = self._generic_metadata(p)
        try:
            import mutagen
            mf = mutagen.File(str(p))
            if mf is not None and mf.info is not None:
                out["duration_s"] = round(float(mf.info.length), 3)
                if hasattr(mf.info, "bitrate"):
                    out["bitrate"] = int(getattr(mf.info, "bitrate", 0))
                if hasattr(mf.info, "sample_rate"):
                    out["sample_rate"] = int(getattr(mf.info, "sample_rate", 0))
        except Exception as exc:
            logger.debug("metadata.audio_failed", error=str(exc))
        return out

    def _video_metadata(self, p: Path) -> dict[str, Any]:
        out = self._generic_metadata(p)
        try:
            # Try to find "mvhd" duration via raw box parsing
            with p.open("rb") as f:
                data = f.read(64 * 1024)
            idx = data.find(b"mvhd")
            if idx > 0 and idx + 20 < len(data):
                version = data[idx + 8]
                if version == 1 and idx + 32 < len(data):
                    ts = struct.unpack(">I", data[idx + 28:idx + 32])[0]
                else:
                    ts = struct.unpack(">I", data[idx + 20:idx + 24])[0]
                timescale = struct.unpack(">I", data[idx + 24:idx + 28])[0]
                if timescale:
                    out["duration_s"] = round(ts / timescale, 3)
        except OSError:
            pass
        except Exception as exc:
            logger.debug("metadata.video_failed", error=str(exc))
        return out


metadata_service = MetadataService()


__all__ = ["MetadataService", "metadata_service"]
