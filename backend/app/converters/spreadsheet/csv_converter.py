"""CSV / TSV converter — exports tabular data to spreadsheet formats."""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class SpreadsheetCSVConverter(BaseConverter):
    name = "csv-converter"
    backend = "openpyxl+libreoffice"
    category = "spreadsheet"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("csv", "xlsx", 5, "openpyxl", 2.0),
            ConversionEdge("tsv", "xlsx", 5, "openpyxl", 2.0),
            ConversionEdge("csv", "pdf", 4, "libreoffice", 6.0),
            ConversionEdge("tsv", "pdf", 4, "libreoffice", 6.0),
            ConversionEdge("csv", "json", 5, "pandas", 2.0),
            ConversionEdge("csv", "html", 5, "pandas", 2.0),
            ConversionEdge("tsv", "json", 5, "pandas", 2.0),
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
        delim = "\t" if ext == "tsv" else ","

        try:
            if target == "xlsx":
                return await self._to_xlsx(input_path, output_dir, delim, started)
            if target == "json":
                return await self._to_json(input_path, output_dir, delim, started)
            if target == "html":
                return await self._to_html(input_path, output_dir, delim, started)
            if target == "pdf":
                if not backends.libreoffice.is_available():
                    return self._build_result(
                        None, backend="libreoffice", started=started,
                        error=RuntimeError("LibreOffice is required for CSV→PDF."),
                    )
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format="pdf", timeout_s=options.timeout_s,
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

    async def _to_xlsx(
        self,
        input_path: Path,
        output_dir: Path,
        delim: str,
        started: float,
    ) -> ConversionResult:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        with input_path.open("r", encoding="utf-8", newline="") as f:
            for row in f:
                cells = row.rstrip("\n").split(delim)
                ws.append(cells)
        out = self.make_output_path(output_dir, "xlsx")
        wb.save(out)
        return self._build_result(out, backend="openpyxl", started=started)

    async def _to_json(
        self,
        input_path: Path,
        output_dir: Path,
        delim: str,
        started: float,
    ) -> ConversionResult:
        import csv
        import json

        with input_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=delim)
            rows = list(reader)
        out = self.make_output_path(output_dir, "json")
        out.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return self._build_result(out, backend="csv", started=started)

    async def _to_html(
        self,
        input_path: Path,
        output_dir: Path,
        delim: str,
        started: float,
    ) -> ConversionResult:
        import csv

        out = self.make_output_path(output_dir, "html")
        with input_path.open("r", encoding="utf-8", newline="") as f, out.open(
            "w", encoding="utf-8"
        ) as g:
            g.write("<!doctype html><html><head><meta charset='utf-8'></head><body><table border='1'>")
            for row in csv.reader(f, delimiter=delim):
                g.write("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
            g.write("</table></body></html>")
        return self._build_result(out, backend="csv", started=started)
