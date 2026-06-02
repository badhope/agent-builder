"""YAML converter — to JSON, XML."""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class YAMLConverter(BaseConverter):
    name = "yaml-converter"
    backend = "native"
    category = "data"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("yaml", "json", 5, "native", 1.0),
            ConversionEdge("yml", "json", 5, "native", 1.0),
            ConversionEdge("yaml", "xml", 5, "native", 1.0),
            ConversionEdge("yaml", "txt", 4, "native", 1.0),
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
            with input_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:
            return self._build_result(
                None, backend=self.backend, started=started,
                error=ValueError(f"Invalid YAML: {exc}"),
            )

        try:
            if target == "json":
                out = self.make_output_path(output_dir, "json")
                out.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
            if target == "xml":
                # Reuse the JSON converter's logic
                from app.converters.data.json_converter import _json_to_xml
                out = self.make_output_path(output_dir, "xml")
                out.write_text(_json_to_xml(data), encoding="utf-8")
                return self._build_result(out, backend="native", started=started)
            if target == "txt":
                out = self.make_output_path(output_dir, "txt")
                out.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None, backend=self.backend, started=started,
            error=ValueError(f"Unsupported yaml→{target}"),
        )
