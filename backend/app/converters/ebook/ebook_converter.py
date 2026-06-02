"""Ebook converter — wraps MOBI/AZW3 → other formats.

For full MOBI support we recommend installing ``ebooklib`` and
``pypandoc``; we also try ``libreoffice`` as a fallback.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class EbookConverter(BaseConverter):
    name = "ebook-converter"
    backend = "libreoffice+pypandoc"
    category = "ebook"

    def supported_edges(self) -> list[ConversionEdge]:
        edges: list[ConversionEdge] = []
        for src in ("mobi", "azw", "azw3", "fb2"):
            for tgt in ("epub", "pdf", "txt", "html"):
                edges.append(ConversionEdge(src, tgt, 3, "libreoffice-or-pandoc", 10.0))
        return edges

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
            if backends.libreoffice.is_available() and target in {"pdf", "epub"}:
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format=target, timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                )
            if backends.pandoc.is_available():
                output = self.make_output_path(output_dir, target)
                backends.pandoc.convert(
                    input_path, output,
                    from_format=ext, to_format=target,
                    timeout_s=options.timeout_s,
                )
                return self._build_result(
                    output, backend="pypandoc", started=started,
                )
            return self._build_result(
                None, backend=self.backend, started=started,
                error=RuntimeError(
                    "Neither LibreOffice nor pandoc is available for ebook conversion."
                ),
            )
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)
