"""EPUB converter — uses pypandoc as the primary engine."""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class EPUBConverter(BaseConverter):
    name = "epub-converter"
    backend = "pypandoc+libreoffice"
    category = "ebook"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("epub", "pdf", 4, "libreoffice", 8.0),
            ConversionEdge("epub", "docx", 4, "pypandoc", 5.0),
            ConversionEdge("epub", "html", 5, "pypandoc", 3.0),
            ConversionEdge("epub", "md", 5, "pypandoc", 3.0),
            ConversionEdge("epub", "txt", 4, "pypandoc", 3.0),
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
            if target == "pdf":
                if not backends.libreoffice.is_available():
                    return self._build_result(
                        None, backend="libreoffice", started=started,
                        error=RuntimeError("LibreOffice is required for EPUB→PDF."),
                    )
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format="pdf", timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                )
            # pandoc handles the rest
            if not backends.pandoc.is_available():
                return self._build_result(
                    None, backend="pypandoc", started=started,
                    error=RuntimeError("Pandoc is required."),
                )
            output = self.make_output_path(output_dir, target)
            backends.pandoc.convert(
                input_path, output,
                from_format="epub", to_format=target,
                timeout_s=options.timeout_s,
            )
            return self._build_result(
                output, backend="pypandoc", started=started,
            )
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)
