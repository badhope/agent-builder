"""Markdown converter — uses pypandoc for high-fidelity prose conversions,
weasyprint for HTML→PDF."""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class MarkdownConverter(BaseConverter):
    name = "markdown-converter"
    backend = "pypandoc+weasyprint"
    category = "markup"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("md", "html", 5, "pypandoc", 2.0),
            ConversionEdge("md", "pdf", 4, "weasyprint", 5.0),
            ConversionEdge("md", "docx", 5, "pypandoc", 3.0),
            ConversionEdge("md", "txt", 5, "pypandoc", 2.0),
            ConversionEdge("md", "epub", 4, "pypandoc", 5.0),
            ConversionEdge("md", "rst", 4, "pypandoc", 2.0),
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
                # Two-step: md → html via pandoc, then html → pdf via weasyprint
                if not backends.pandoc.is_available():
                    return self._build_result(
                        None, backend="weasyprint", started=started,
                        error=RuntimeError("Pandoc is required for md→pdf."),
                    )
                with self.temp_workdir() as tmp:
                    html_path = tmp / "out.html"
                    backends.pandoc.convert(
                        input_path, html_path,
                        from_format="markdown", to_format="html",
                        timeout_s=options.timeout_s,
                    )
                    if not backends.weasyprint_backend.is_available():
                        return self._build_result(
                            None, backend="weasyprint", started=started,
                            error=RuntimeError("WeasyPrint is required for md→pdf."),
                        )
                    output = self.make_output_path(output_dir, "pdf")
                    backends.weasyprint_backend.html_to_pdf(html_path, output)
                    return self._build_result(
                        output, backend="pandoc+weasyprint", started=started,
                        steps=[
                            {"name": "pandoc", "status": "ok"},
                            {"name": "weasyprint", "status": "ok"},
                        ],
                    )

            if not backends.pandoc.is_available():
                return self._build_result(
                    None, backend="pypandoc", started=started,
                    error=RuntimeError("Pandoc is required."),
                )
            output = self.make_output_path(output_dir, target)
            backends.pandoc.convert(
                input_path, output,
                from_format="markdown", to_format=target,
                timeout_s=options.timeout_s,
            )
            return self._build_result(
                output, backend="pypandoc", started=started,
            )
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)
