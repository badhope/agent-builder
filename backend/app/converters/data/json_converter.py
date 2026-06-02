"""JSON converter — to XML, YAML, CSV."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

import yaml

from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class JSONConverter(BaseConverter):
    name = "json-converter"
    backend = "native"
    category = "data"

    def supported_edges(self) -> list[ConversionEdge]:
        return [
            ConversionEdge("json", "yaml", 5, "native", 1.0),
            ConversionEdge("json", "yml", 5, "native", 1.0),
            ConversionEdge("json", "xml", 5, "native", 1.0),
            ConversionEdge("json", "csv", 4, "native", 2.0),
            ConversionEdge("json", "txt", 4, "native", 1.0),
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
            data = json.loads(input_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return self._build_result(
                None, backend=self.backend, started=started,
                error=ValueError(f"Invalid JSON: {exc}"),
            )

        try:
            if target in {"yaml", "yml"}:
                out = self.make_output_path(output_dir, "yaml")
                out.write_text(
                    yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
            if target == "xml":
                out = self.make_output_path(output_dir, "xml")
                out.write_text(_json_to_xml(data), encoding="utf-8")
                return self._build_result(out, backend="native", started=started)
            if target == "csv":
                out = self.make_output_path(output_dir, "csv")
                _json_to_csv(data, out)
                return self._build_result(out, backend="native", started=started)
            if target == "txt":
                out = self.make_output_path(output_dir, "txt")
                out.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
                )
                return self._build_result(out, backend="native", started=started)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

        return self._build_result(
            None, backend=self.backend, started=started,
            error=ValueError(f"Unsupported json→{target}"),
        )


# ---- helpers ----


def _json_to_xml(value: Any, root_tag: str = "root") -> str:
    """Best-effort JSON→XML serialisation.

    JSON arrays and objects are mapped to repeated / nested XML elements.
    Scalars become element text content.
    """
    parts = ['<?xml version="1.0" encoding="utf-8"?>']

    def _emit(v: Any, tag: str) -> str:
        if isinstance(v, dict):
            inner = "".join(_emit(val, _safe_tag(k)) for k, val in v.items())
            return f"<{tag}>{inner}</{tag}>"
        if isinstance(v, list):
            return "".join(_emit(item, "item") for item in v)
        if v is None:
            return f"<{tag} />"
        if isinstance(v, bool):
            return f"<{tag}>{'true' if v else 'false'}</{tag}>"
        return f"<{tag}>{_xml_escape(str(v))}</{tag}>"

    parts.append(_emit(value, root_tag))
    return "".join(parts)


def _safe_tag(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(name))
    if safe and safe[0].isdigit():
        safe = "_" + safe
    return safe or "_"


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _json_to_csv(data: Any, output: Path) -> None:
    """Flatten simple JSON array-of-objects into CSV."""
    if isinstance(data, dict):
        # Treat single object as a one-row table
        rows = [data]
    elif isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    else:
        rows = [{"value": data}]

    if not rows:
        output.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)

    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: _flatten_scalar(r.get(k)) for k in fieldnames})


def _flatten_scalar(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, dict | list):
        return json.dumps(v, ensure_ascii=False, default=str)
    return str(v)
