"""ODT / RTF converters — both routed through LibreOffice."""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class ODTConverter(BaseConverter):
    name = "odt-converter"
    backend = "libreoffice"
    category = "document"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("odt", "pdf", 5, "libreoffice", 4.0),
            ConversionEdge("odt", "docx", 5, "libreoffice", 4.0),
            ConversionEdge("odt", "txt", 4, "libreoffice", 3.0),
            ConversionEdge("odt", "html", 4, "libreoffice", 3.0),
            ConversionEdge("odt", "rtf", 4, "libreoffice", 3.0),
        ]

    async def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
    ) -> ConversionResult:
        started = time.monotonic()
        if not backends.libreoffice.is_available():
            return self._build_result(
                None, backend=self.backend, started=started,
                error=RuntimeError("LibreOffice is required for ODT conversion."),
            )
        try:
            result = backends.libreoffice.convert(
                input_path, output_dir,
                target_format=options.target_format.lower(),
                timeout_s=options.timeout_s,
            )
            return self._build_result(
                result.output_path, backend=self.backend, started=started,
                steps=[{"name": "libreoffice", "status": "ok"}],
            )
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)


class RTFConverter(BaseConverter):
    name = "rtf-converter"
    backend = "libreoffice"
    category = "document"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("rtf", "pdf", 4, "libreoffice", 4.0),
            ConversionEdge("rtf", "docx", 4, "libreoffice", 4.0),
            ConversionEdge("rtf", "txt", 4, "libreoffice", 3.0),
            ConversionEdge("rtf", "html", 3, "libreoffice", 3.0),
            ConversionEdge("rtf", "odt", 4, "libreoffice", 4.0),
        ]

    async def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
    ) -> ConversionResult:
        started = time.monotonic()
        if not backends.libreoffice.is_available():
            return self._build_result(
                None, backend=self.backend, started=started,
                error=RuntimeError("LibreOffice is required for RTF conversion."),
            )
        try:
            result = backends.libreoffice.convert(
                input_path, output_dir,
                target_format=options.target_format.lower(),
                timeout_s=options.timeout_s,
            )
            return self._build_result(
                result.output_path, backend=self.backend, started=started,
                steps=[{"name": "libreoffice", "status": "ok"}],
            )
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)
