"""PDF converter.

Targets (and engines):

* PDF → DOCX  : pdfplumber (text extraction) → python-docx (assembly)
* PDF → TXT   : pdfplumber
* PDF → HTML  : pdfplumber + a simple HTML wrapper
* PDF → MD    : pdfplumber text
* PDF → EPUB  : ebooklib (assemble simple EPUB from extracted text)
* PDF → PNG/JPG : pdf2image (one image per page → bundled as ZIP via caller)
* PDF → JSON  : pdfplumber metadata + per-page text

The high-fidelity ``PDF → DOCX`` pipeline is delegated to LibreOffice
when ``options.quality >= HIGH`` and the input is a "born-digital" PDF
(no scanned pages); otherwise we fall back to the text-extraction path.
"""

from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class PDFConverter(BaseConverter):
    name = "pdf-converter"
    backend = "mixed"
    category = "document"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("pdf", "docx", 4, "libreoffice-or-pdfplumber", 8.0),
            ConversionEdge("pdf", "txt", 5, "pdfplumber", 2.0),
            ConversionEdge("pdf", "html", 4, "pdfplumber", 4.0),
            ConversionEdge("pdf", "md", 4, "pdfplumber", 4.0),
            ConversionEdge("pdf", "epub", 3, "ebooklib", 12.0),
            ConversionEdge("pdf", "json", 5, "pdfplumber", 3.0),
            ConversionEdge("pdf", "png", 4, "pdf2image", 10.0),
            ConversionEdge("pdf", "jpg", 4, "pdf2image", 10.0),
        ]

    async def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
    ) -> ConversionResult:
        started = time.monotonic()
        target = options.target_format.lower()

        try:
            if target == "docx":
                return await self._to_docx(input_path, output_dir, options, started)
            if target == "txt":
                return await self._to_text(input_path, output_dir, options, started)
            if target in {"html", "md"}:
                return await self._to_markup(input_path, output_dir, options, started, target)
            if target == "epub":
                return await self._to_epub(input_path, output_dir, options, started)
            if target == "json":
                return await self._to_json(input_path, output_dir, options, started)
            if target in {"png", "jpg", "jpeg"}:
                return await self._to_images(input_path, output_dir, options, started, target)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None,
            backend=self.backend,
            started=started,
            error=ValueError(f"Unsupported PDF target: {target}"),
        )

    # ---- Per-target implementations ----

    async def _to_docx(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
    ) -> ConversionResult:
        """Try LibreOffice first (best fidelity), fall back to python-docx."""
        if backends.libreoffice.is_available() and options.quality.value in {"high", "lossless"}:
            try:
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format="docx", timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                    steps=[{"name": "libreoffice", "status": "ok"}],
                )
            except Exception:
                # Fall through to python-docx path
                pass

        # Fallback: extract text with pdfplumber and assemble a docx
        try:
            import pdfplumber
            from docx import Document
        except ImportError as exc:
            return self._build_result(
                None, backend="python-docx", started=started,
                error=RuntimeError(f"Required library missing: {exc}"),
            )

        output = self.make_output_path(output_dir, "docx")
        doc = Document()
        with pdfplumber.open(input_path) as pdf:
            for i, page in enumerate(pdf.pages):
                if i > 0:
                    doc.add_page_break()
                text = page.extract_text() or ""
                for line in text.splitlines():
                    doc.add_paragraph(line)
        doc.save(output)
        return self._build_result(
            output, backend="python-docx", started=started,
            steps=[{"name": "pdfplumber", "status": "ok"}],
        )

    async def _to_text(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
    ) -> ConversionResult:
        import pdfplumber

        output = self.make_output_path(output_dir, "txt")
        with pdfplumber.open(input_path) as pdf, output.open("w", encoding="utf-8") as f:
            for page in pdf.pages:
                f.write(page.extract_text() or "")
                f.write("\n\n")
        return self._build_result(
            output, backend="pdfplumber", started=started,
            steps=[{"name": "pdfplumber", "status": "ok"}],
        )

    async def _to_markup(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
        target: str,
    ) -> ConversionResult:
        import bleach
        import pdfplumber

        output = self.make_output_path(output_dir, target)
        with pdfplumber.open(input_path) as pdf:
            parts: list[str] = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if target == "html":
                    parts.append(
                        f'<section data-page="{i+1}">'
                        + "<br/>".join(bleach.clean(line) for line in text.splitlines())
                        + "</section>"
                    )
                else:  # md
                    parts.append(f"\n\n<!-- page {i+1} -->\n\n" + text)
            body = "\n".join(parts) if target == "html" else "".join(parts)
            if target == "html":
                body = (
                    '<!doctype html><html><head><meta charset="utf-8">'
                    "<title>Converted document</title></head><body>"
                    + body
                    + "</body></html>"
                )
        output.write_text(body, encoding="utf-8")
        return self._build_result(
            output, backend="pdfplumber", started=started,
            steps=[{"name": "pdfplumber", "status": "ok"}],
        )

    async def _to_epub(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
    ) -> ConversionResult:
        try:
            import pdfplumber
            from ebooklib import epub
        except ImportError as exc:
            return self._build_result(
                None, backend="ebooklib", started=started,
                error=RuntimeError(f"Required library missing: {exc}"),
            )

        book = epub.EpubBook()
        book.set_identifier(f"dfc-{input_path.stem}")
        book.set_title(input_path.stem)
        book.set_language("en")

        chapters: list = []
        with pdfplumber.open(input_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                chapter = epub.EpubHtml(
                    title=f"Page {i+1}",
                    file_name=f"page_{i+1:04d}.xhtml",
                    lang="en",
                )
                chapter.content = (
                    f"<h1>Page {i+1}</h1>"
                    f"<pre>{text}</pre>"
                )
                book.add_item(chapter)
                chapters.append(chapter)

        book.toc = tuple(chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", *chapters]

        output = self.make_output_path(output_dir, "epub")
        epub.write_epub(str(output), book)
        return self._build_result(
            output, backend="ebooklib", started=started,
            steps=[{"name": "ebooklib", "status": "ok"}],
        )

    async def _to_json(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
    ) -> ConversionResult:
        import pdfplumber

        pages_data: list[dict] = []
        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                pages_data.append(
                    {
                        "text": page.extract_text() or "",
                        "width": float(page.width),
                        "height": float(page.height),
                    }
                )
        output = self.make_output_path(output_dir, "json")
        output.write_text(
            json.dumps({"pages": pages_data}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self._build_result(
            output, backend="pdfplumber", started=started,
            steps=[{"name": "pdfplumber", "status": "ok"}],
        )

    async def _to_images(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
        target: str,
    ) -> ConversionResult:
        try:
            from pdf2image import convert_from_path
        except ImportError as exc:
            return self._build_result(
                None, backend="pdf2image", started=started,
                error=RuntimeError(f"Required library missing: {exc}"),
            )

        images = convert_from_path(input_path, dpi=200)
        if not images:
            return self._build_result(
                None, backend="pdf2image", started=started,
                error=ValueError("PDF has no pages."),
            )

        ext = "jpg" if target in ("jpg", "jpeg") else "png"
        page_files: list[Path] = []
        for i, img in enumerate(images, start=1):
            p = output_dir / f"page_{i:04d}.{ext}"
            img.save(p, format="JPEG" if ext == "jpg" else "PNG")
            page_files.append(p)

        # Bundle into a zip
        zip_path = self.make_output_path(output_dir, "zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in page_files:
                zf.write(p, arcname=p.name)
        return self._build_result(
            zip_path, backend="pdf2image", started=started,
            steps=[{"name": "pdf2image", "status": "ok", "pages": len(page_files)}],
        )
