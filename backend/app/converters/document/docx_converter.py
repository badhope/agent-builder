"""DOCX converter."""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class DOCXConverter(BaseConverter):
    name = "docx-converter"
    backend = "libreoffice+pypandoc"
    category = "document"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("docx", "pdf", 5, "libreoffice", 5.0),
            ConversionEdge("docx", "odt", 5, "libreoffice", 3.0),
            ConversionEdge("docx", "html", 4, "pypandoc", 3.0),
            ConversionEdge("docx", "md", 4, "pypandoc", 3.0),
            ConversionEdge("docx", "txt", 4, "python-docx", 2.0),
            ConversionEdge("docx", "rtf", 4, "libreoffice", 3.0),
            ConversionEdge("docx", "epub", 4, "pypandoc", 5.0),
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
            if target in {"pdf", "odt", "rtf"}:
                if not backends.libreoffice.is_available():
                    return self._build_result(
                        None, backend="libreoffice", started=started,
                        error=RuntimeError("LibreOffice is required for this conversion."),
                    )
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format=target, timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                    steps=[{"name": "libreoffice", "status": "ok"}],
                )
            if target in {"html", "md", "epub"}:
                if not backends.pandoc.is_available():
                    return self._build_result(
                        None, backend="pypandoc", started=started,
                        error=RuntimeError("Pandoc is required for this conversion."),
                    )
                output = self.make_output_path(output_dir, target)
                backends.pandoc.convert(
                    input_path, output,
                    from_format="docx", to_format=target,
                    timeout_s=options.timeout_s,
                )
                return self._build_result(
                    output, backend="pypandoc", started=started,
                    steps=[{"name": "pandoc", "status": "ok"}],
                )
            if target == "txt":
                return await self._to_text(input_path, output_dir, started)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None, backend=self.backend, started=started,
            error=ValueError(f"Unsupported DOCX target: {target}"),
        )

    async def _to_text(
        self, input_path: Path, output_dir: Path, started: float,
    ) -> ConversionResult:
        from docx import Document

        doc = Document(input_path)
        output = self.make_output_path(output_dir, "txt")
        with output.open("w", encoding="utf-8") as f:
            for para in doc.paragraphs:
                f.write(para.text)
                f.write("\n")
        return self._build_result(
            output, backend="python-docx", started=started,
            steps=[{"name": "python-docx", "status": "ok"}],
        )
