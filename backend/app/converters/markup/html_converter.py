"""HTML converter."""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class HTMLConverter(BaseConverter):
    name = "html-converter"
    backend = "pypandoc+weasyprint"
    category = "markup"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("html", "pdf", 5, "weasyprint", 5.0),
            ConversionEdge("html", "md", 5, "pypandoc", 2.0),
            ConversionEdge("html", "txt", 4, "pypandoc", 2.0),
            ConversionEdge("html", "docx", 4, "pypandoc", 3.0),
            ConversionEdge("htm", "pdf", 5, "weasyprint", 5.0),
            ConversionEdge("htm", "md", 5, "pypandoc", 2.0),
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
                if not backends.weasyprint_backend.is_available():
                    return self._build_result(
                        None, backend="weasyprint", started=started,
                        error=RuntimeError("WeasyPrint is required for HTML→PDF."),
                    )
                output = self.make_output_path(output_dir, "pdf")
                backends.weasyprint_backend.html_to_pdf(input_path, output)
                return self._build_result(output, backend="weasyprint", started=started)

            if not backends.pandoc.is_available():
                return self._build_result(
                    None, backend="pypandoc", started=started,
                    error=RuntimeError("Pandoc is required."),
                )
            output = self.make_output_path(output_dir, target)
            backends.pandoc.convert(
                input_path, output,
                from_format="html", to_format=target,
                timeout_s=options.timeout_s,
            )
            return self._build_result(output, backend="pypandoc", started=started)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)
