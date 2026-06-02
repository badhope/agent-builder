"""PPTX / PPT / ODP converter."""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class PPTXConverter(BaseConverter):
    name = "pptx-converter"
    backend = "libreoffice+python-pptx"
    category = "presentation"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("pptx", "pdf", 5, "libreoffice", 10.0),
            ConversionEdge("pptx", "odp", 5, "libreoffice", 5.0),
            ConversionEdge("pptx", "txt", 4, "python-pptx", 3.0),
            ConversionEdge("pptx", "html", 4, "python-pptx", 5.0),
            ConversionEdge("pptx", "png", 4, "libreoffice+pdf2image", 15.0),
            ConversionEdge("ppt", "pptx", 4, "libreoffice", 5.0),
            ConversionEdge("ppt", "pdf", 4, "libreoffice", 10.0),
            ConversionEdge("odp", "pptx", 4, "libreoffice", 5.0),
            ConversionEdge("odp", "pdf", 4, "libreoffice", 10.0),
        ]

    async def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
    ) -> ConversionResult:
        started = time.monotonic()
        target = options.target_format.lower()
        ext = input_path.suffix.lower().lstrip(".")

        try:
            if ext in {"ppt", "pptx"} and target in {"pptx", "pdf", "odp"}:
                if ext == "pptx" and target == "txt":
                    return await self._to_text(input_path, output_dir, started)
                if ext == "pptx" and target == "html":
                    return await self._to_html(input_path, output_dir, started)
                if target == "png" and ext == "pptx":
                    return await self._to_png_via_pdf(
                        input_path, output_dir, options, started
                    )
                if not backends.libreoffice.is_available():
                    return self._build_result(
                        None, backend="libreoffice", started=started,
                        error=RuntimeError("LibreOffice is required."),
                    )
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format=target, timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                )

            if ext == "odp" and target in {"pptx", "pdf"}:
                if not backends.libreoffice.is_available():
                    return self._build_result(
                        None, backend="libreoffice", started=started,
                        error=RuntimeError("LibreOffice is required."),
                    )
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format=target, timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                )
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None, backend=self.backend, started=started,
            error=ValueError(f"Unsupported {ext}→{target} conversion."),
        )

    async def _to_text(
        self,
        input_path: Path,
        output_dir: Path,
        started: float,
    ) -> ConversionResult:
        from pptx import Presentation

        prs = Presentation(input_path)
        out = self.make_output_path(output_dir, "txt")
        with out.open("w", encoding="utf-8") as f:
            for i, slide in enumerate(prs.slides, start=1):
                f.write(f"--- Slide {i} ---\n")
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            f.write(para.text + "\n")
                f.write("\n")
        return self._build_result(out, backend="python-pptx", started=started)

    async def _to_html(
        self,
        input_path: Path,
        output_dir: Path,
        started: float,
    ) -> ConversionResult:
        from pptx import Presentation

        prs = Presentation(input_path)
        out = self.make_output_path(output_dir, "html")
        parts = [
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Slides</title></head><body>"
        ]
        for i, slide in enumerate(prs.slides, start=1):
            parts.append(f"<section><h2>Slide {i}</h2>")
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        parts.append(f"<p>{para.text}</p>")
            parts.append("</section>")
        parts.append("</body></html>")
        out.write_text("".join(parts), encoding="utf-8")
        return self._build_result(out, backend="python-pptx", started=started)

    async def _to_png_via_pdf(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
    ) -> ConversionResult:
        if not backends.libreoffice.is_available():
            return self._build_result(
                None, backend="libreoffice+pdf2image", started=started,
                error=RuntimeError("LibreOffice is required for PPTX→PNG."),
            )
        # First convert to PDF in a temp dir
        with self.temp_workdir() as tmp:
            pdf_result = backends.libreoffice.convert(
                input_path, tmp, target_format="pdf", timeout_s=options.timeout_s,
            )
            try:
                from pdf2image import convert_from_path
            except ImportError as exc:
                return self._build_result(
                    None, backend="pdf2image", started=started,
                    error=RuntimeError(f"pdf2image missing: {exc}"),
                )
            images = convert_from_path(pdf_result.output_path, dpi=150)
            for i, img in enumerate(images, start=1):
                img.save(output_dir / f"slide_{i:04d}.png", format="PNG")
        zip_path = self.make_output_path(output_dir, "zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(output_dir.glob("slide_*.png")):
                zf.write(p, arcname=p.name)
        return self._build_result(
            zip_path, backend="libreoffice+pdf2image", started=started,
            steps=[{"name": "libreoffice", "status": "ok"},
                   {"name": "pdf2image", "status": "ok", "pages": len(images)}],
        )
