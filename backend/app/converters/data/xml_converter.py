"""XML converter — to JSON, YAML, CSV (data path)."""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class XMLConverter(BaseConverter):
    name = "xml-converter"
    backend = "native"
    category = "data"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("xml", "json", 5, "native", 1.0),
            ConversionEdge("xml", "yaml", 5, "native", 1.0),
            ConversionEdge("xml", "yml", 5, "native", 1.0),
            ConversionEdge("xml", "txt", 4, "native", 1.0),
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
            tree = ET.parse(input_path)
            root = tree.getroot()
            data = _xml_to_json(root)
        except Exception as exc:
            return self._build_result(
                None, backend=self.backend, started=started,
                error=ValueError(f"Invalid XML: {exc}"),
            )

        try:
            if target == "json":
                out = self.make_output_path(output_dir, "json")
                out.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
            if target in {"yaml", "yml"}:
                out = self.make_output_path(output_dir, "yaml")
                out.write_text(
                    yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
            if target == "txt":
                out = self.make_output_path(output_dir, "txt")
                out.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
                return self._build_result(out, backend="native", started=started)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None, backend=self.backend, started=started,
            error=ValueError(f"Unsupported xml→{target}"),
        )


def _xml_to_json(elem: ET.Element) -> Any:
    result: dict[str, Any] = {}
    for k, v in elem.attrib.items():
        result[f"@{k}"] = v

    children = list(elem)
    if not children:
        if elem.text and elem.text.strip():
            return elem.text.strip()
        if not result:
            return ""
        return result

    for child in children:
        value = _xml_to_json(child)
        if child.tag in result:
            existing = result[child.tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[child.tag] = [existing, value]
        else:
            result[child.tag] = value

    if elem.text and elem.text.strip():
        result["#text"] = elem.text.strip()

    return result
