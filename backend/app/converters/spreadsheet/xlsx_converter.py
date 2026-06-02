"""XLSX / XLS / ODS converter — uses openpyxl/pandas as primary engines,
LibreOffice as fallback for high-fidelity XLSX → PDF."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class XLSXConverter(BaseConverter):
    name = "xlsx-converter"
    backend = "openpyxl+libreoffice"
    category = "spreadsheet"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("xlsx", "csv", 5, "openpyxl", 2.0),
            ConversionEdge("xlsx", "tsv", 5, "openpyxl", 2.0),
            ConversionEdge("xlsx", "json", 4, "openpyxl", 2.0),
            ConversionEdge("xlsx", "html", 4, "openpyxl", 3.0),
            ConversionEdge("xlsx", "xlsx", 5, "openpyxl", 2.0),  # normalize
            ConversionEdge("xlsx", "pdf", 4, "libreoffice", 8.0),
            ConversionEdge("xlsx", "ods", 4, "libreoffice", 5.0),
            ConversionEdge("xls", "xlsx", 4, "libreoffice", 5.0),
            ConversionEdge("xls", "csv", 4, "xlrd", 3.0),
            ConversionEdge("xls", "pdf", 4, "libreoffice", 8.0),
            ConversionEdge("ods", "xlsx", 4, "libreoffice", 5.0),
            ConversionEdge("ods", "csv", 4, "libreoffice", 3.0),
            ConversionEdge("ods", "pdf", 4, "libreoffice", 8.0),
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
            # xlsx + xls + ods → csv/tsv/json/html
            if ext == "xlsx" and target in {"csv", "tsv", "json", "html", "xlsx"}:
                return await self._xlsx_to_table(input_path, output_dir, target, started)

            if ext == "xls" and target in {"csv", "xlsx", "pdf"}:
                if target == "csv":
                    return await self._xls_to_csv(input_path, output_dir, started)
                # xls → xlsx / pdf need LibreOffice
                if not backends.libreoffice.is_available():
                    return self._build_result(
                        None, backend="libreoffice", started=started,
                        error=RuntimeError("LibreOffice is required for xls→xlsx/pdf."),
                    )
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format=target, timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                )

            if ext == "ods":
                if not backends.libreoffice.is_available():
                    return self._build_result(
                        None, backend="libreoffice", started=started,
                        error=RuntimeError("LibreOffice is required for ODS conversion."),
                    )
                result = backends.libreoffice.convert(
                    input_path, output_dir, target_format=target, timeout_s=options.timeout_s,
                )
                return self._build_result(
                    result.output_path, backend="libreoffice", started=started,
                )

            if ext == "xlsx" and target in {"pdf", "ods"}:
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
                )
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None, backend=self.backend, started=started,
            error=ValueError(f"Unsupported {ext}→{target} conversion."),
        )

    # ---- Per-target implementations ----

    async def _xlsx_to_table(
        self,
        input_path: Path,
        output_dir: Path,
        target: str,
        started: float,
    ) -> ConversionResult:
        from openpyxl import load_workbook

        wb = load_workbook(input_path, data_only=True, read_only=True)
        try:
            sheets: dict[str, list[list]] = {}
            for ws in wb.worksheets:
                rows: list[list] = []
                for row in ws.iter_rows(values_only=True):
                    rows.append(["" if v is None else v for v in row])
                sheets[ws.title] = rows

            if target in {"csv", "tsv"}:
                delim = "\t" if target == "tsv" else ","
                out = self.make_output_path(output_dir, target)
                with out.open("w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f, delimiter=delim)
                    # Write first sheet only
                    first = next(iter(sheets.values())) if sheets else []
                    for row in first:
                        w.writerow(row)
                return self._build_result(
                    out, backend="openpyxl", started=started,
                    steps=[{"name": "openpyxl", "status": "ok", "sheets": len(sheets)}],
                )

            if target == "json":
                out = self.make_output_path(output_dir, "json")
                out.write_text(
                    json.dumps(sheets, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                return self._build_result(
                    out, backend="openpyxl", started=started,
                    steps=[{"name": "openpyxl", "status": "ok"}],
                )

            if target == "html":
                out = self.make_output_path(output_dir, "html")
                parts = ["<!doctype html><html><head><meta charset='utf-8'>"
                         "<title>Spreadsheet</title></head><body>"]
                for name, rows in sheets.items():
                    parts.append(f"<h2>{name}</h2><table border='1'>")
                    for row in rows:
                        parts.append("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>")
                    parts.append("</table>")
                parts.append("</body></html>")
                out.write_text("".join(parts), encoding="utf-8")
                return self._build_result(out, backend="openpyxl", started=started)

            if target == "xlsx":
                # Normalize: re-save the workbook (trims any corruption)
                from openpyxl import load_workbook as _lw
                wb2 = _lw(input_path)
                out = self.make_output_path(output_dir, "xlsx")
                wb2.save(out)
                return self._build_result(out, backend="openpyxl", started=started)
        finally:
            wb.close()

        return self._build_result(
            None, backend="openpyxl", started=started,
            error=ValueError(f"Unsupported target: {target}"),
        )

    async def _xls_to_csv(
        self,
        input_path: Path,
        output_dir: Path,
        started: float,
    ) -> ConversionResult:
        try:
            import xlrd
        except ImportError as exc:
            return self._build_result(
                None, backend="xlrd", started=started,
                error=RuntimeError(f"xlrd required: {exc}"),
            )

        book = xlrd.open_workbook(str(input_path))
        sh = book.sheet_by_index(0)
        out = self.make_output_path(output_dir, "csv")
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for r in range(sh.nrows):
                w.writerow(sh.row_values(r))
        return self._build_result(out, backend="xlrd", started=started)
