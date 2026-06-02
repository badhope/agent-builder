"""Generic CSV converter (separate from the spreadsheet-aware one).

This converter handles text/CSV ⇄ JSON/YAML. Tabular CSV (→ xlsx) is
handled by :class:`SpreadsheetCSVConverter`.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import yaml

from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class CSVConverter(BaseConverter):
    name = "csv-data-converter"
    backend = "native"
    category = "data"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("csv", "json", 5, "native", 1.0),
            ConversionEdge("csv", "yaml", 5, "native", 1.0),
            ConversionEdge("tsv", "json", 5, "native", 1.0),
            ConversionEdge("tsv", "yaml", 5, "native", 1.0),
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
            with input_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f, delimiter=delim)
                rows = list(reader)
        except Exception as exc:
            return self._build_result(
                None, backend=self.backend, started=started,
                error=ValueError(f"Invalid CSV: {exc}"),
            )

        try:
            if target == "json":
                out = self.make_output_path(output_dir, "json")
                out.write_text(
                    json.dumps(rows, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
            if target == "yaml":
                out = self.make_output_path(output_dir, "yaml")
                out.write_text(
                    yaml.safe_dump(rows, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None, backend=self.backend, started=started,
            error=ValueError(f"Unsupported {ext}→{target}"),
        )
