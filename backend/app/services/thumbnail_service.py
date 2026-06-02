"""Thumbnail generation.

Generates a small (256×256) preview image for a file on disk. Returns the
encoded PNG bytes (no storage side effects — the caller decides what to do
with them). Errors are swallowed and logged.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Final

from app.core.magic_bytes import is_text_format
from app.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_SIZE: Final[int] = 256


class ThumbnailService:
    """Generate a thumbnail for a stored file."""

    async def generate(
        self, file_path: Path, fmt: str | None, size: int = DEFAULT_SIZE,
    ) -> bytes | None:
        if not file_path.exists():
            return None
        fmt_l = (fmt or "").lower()
        try:
            if fmt_l == "pdf":
                return self._pdf_thumbnail(file_path, size)
            if fmt_l in {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "tif"}:
                return self._image_thumbnail(file_path, size)
            if fmt_l in {"svg",}:
                return self._svg_thumbnail(file_path, size)
            if is_text_format(fmt_l) or fmt_l in {"md", "markdown", "html", "json", "xml", "csv"}:
                return self._text_thumbnail(file_path, size)
            return None
        except Exception as exc:
            logger.warning("thumbnail.failed", error=str(exc))
            return None

    # ---- format-specific ----

    def _image_thumbnail(self, p: Path, size: int) -> bytes | None:
        try:
            from PIL import Image
            with Image.open(p) as im:
                im.thumbnail((size, size))
                if im.mode in {"RGBA", "P", "LA"}:
                    im = im.convert("RGB")
                buf = io.BytesIO()
                im.save(buf, format="PNG", optimize=True)
                return buf.getvalue()
        except Exception:
            return None

    def _svg_thumbnail(self, p: Path, size: int) -> bytes | None:
        try:
            import cairosvg
            png_bytes = cairosvg.svg2png(  # type: ignore[attr-defined]
                url=str(p), output_width=size, output_height=size,
            )
            return png_bytes
        except Exception:
            return None

    def _pdf_thumbnail(self, p: Path, size: int) -> bytes | None:
        try:
            import pypdfium2 as pdfium  # type: ignore
        except ImportError:
            return None
        try:
            pdf = pdfium.PdfDocument(str(p))
            page = pdf[0]
            pil_image = page.render(scale=size / max(page.get_size())).to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
        except Exception:
            return None

    def _text_thumbnail(self, p: Path, size: int) -> bytes | None:
        try:
            from PIL import Image, ImageDraw, ImageFont
            text = p.read_text(encoding="utf-8", errors="replace")[:2000]
            img = Image.new("RGB", (size, size), color=(245, 245, 245))
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
            # Trivial text rendering; a real implementation would use a TTF.
            for i, line in enumerate(text.splitlines()[:18]):
                draw.text((8, 8 + i * 13), line[:32], fill=(40, 40, 40), font=font)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
        except Exception:
            return None


thumbnail_service = ThumbnailService()


__all__ = ["ThumbnailService", "thumbnail_service"]
