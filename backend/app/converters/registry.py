"""Converter registry — keeps the list of available converters and a
fast source→target lookup.

New converters are registered by importing them and calling
:func:`register`. The :class:`ConverterFactory` then uses the registry
to pick a converter for any ``(source, target)`` request.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.converters.base import BaseConverter, ConversionEdge
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class _Entry:
    converter: BaseConverter
    edge: ConversionEdge


class ConverterRegistry:
    """In-memory index of all available converters."""

    def __init__(self) -> None:
        self._by_edge: dict[tuple[str, str], _Entry] = {}
        self._by_converter: dict[str, list[ConversionEdge]] = {}

    def register(self, converter: BaseConverter) -> None:
        for edge in converter.supported_edges():
            key = (edge.source.lower(), edge.target.lower())
            if key in self._by_edge:
                # First registered wins; warn so duplicate registrations are visible.
                logger.warning(
                    "converter.duplicate_edge",
                    source=edge.source,
                    target=edge.target,
                    existing=self._by_edge[key].converter.name,
                    new=converter.name,
                )
                continue
            self._by_edge[key] = _Entry(converter=converter, edge=edge)
            self._by_converter.setdefault(converter.name, []).append(edge)
        logger.info(
            "converter.registered",
            name=converter.name,
            backend=converter.backend,
            edges=len(converter.supported_edges()),
        )

    def lookup(self, source: str, target: str) -> tuple[BaseConverter, ConversionEdge] | None:
        entry = self._by_edge.get((source.lower(), target.lower()))
        if entry is None:
            return None
        return entry.converter, entry.edge

    def supports(self, source: str, target: str) -> bool:
        return (source.lower(), target.lower()) in self._by_edge

    def all_edges(self) -> list[ConversionEdge]:
        return [e.edge for e in self._by_edge.values()]

    def adjacency_list(self) -> list[dict]:
        return [
            {
                "source": e.source,
                "target": e.target,
                "quality": e.quality,
                "backend": e.backend,
                "estimated_time_s": e.estimated_time_s,
            }
            for e in self.all_edges()
        ]

    def all_formats(self) -> set[str]:
        out: set[str] = set()
        for e in self._by_edge.values():
            out.add(e.edge.source)
            out.add(e.edge.target)
        return out

    def targets_for(self, source: str) -> list[ConversionEdge]:
        return [
            e.edge
            for key, e in self._by_edge.items()
            if key[0] == source.lower()
        ]


# ---- Module-level singleton -------------------------------------------------

_REGISTRY: ConverterRegistry | None = None


def get_registry() -> ConverterRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ConverterRegistry()
        _autoload(_REGISTRY)
    return _REGISTRY


def reset_registry() -> None:
    """Clear and re-autoload (used in tests)."""
    global _REGISTRY
    _REGISTRY = None


def _autoload(registry: ConverterRegistry) -> None:
    """Import and register all built-in converters.

    Import errors are caught and logged — a missing optional dependency
    should not prevent the rest of the system from booting.
    """
    from app.converters import (  # noqa: F401
        data,
        document,
        ebook,
        image,
        markup,
        presentation,
        spreadsheet,
    )
    from app.converters.data.csv_converter import CSVConverter
    from app.converters.data.json_converter import JSONConverter
    from app.converters.data.xml_converter import XMLConverter
    from app.converters.data.yaml_converter import YAMLConverter
    from app.converters.document.docx_converter import DOCXConverter
    from app.converters.document.epub_converter import EPUBConverter
    from app.converters.document.odt_converter import ODTConverter, RTFConverter
    from app.converters.document.pdf_converter import PDFConverter
    from app.converters.ebook.ebook_converter import EbookConverter
    from app.converters.image.image_converter import ImageConverter
    from app.converters.markup.html_converter import HTMLConverter
    from app.converters.markup.markdown_converter import MarkdownConverter
    from app.converters.presentation.pptx_converter import PPTXConverter
    from app.converters.spreadsheet.csv_converter import SpreadsheetCSVConverter
    from app.converters.spreadsheet.xlsx_converter import XLSXConverter

    for cls in (
        PDFConverter,
        DOCXConverter,
        ODTConverter,
        RTFConverter,
        EPUBConverter,
        XLSXConverter,
        SpreadsheetCSVConverter,
        PPTXConverter,
        MarkdownConverter,
        HTMLConverter,
        JSONConverter,
        XMLConverter,
        YAMLConverter,
        CSVConverter,
        ImageConverter,
        EbookConverter,
    ):
        try:
            registry.register(cls())
        except Exception as exc:
            logger.error(  # noqa: TRY400
                "converter.init_failed",
                converter=cls.__name__,
                error=str(exc),
            )


__all__ = [
    "ConverterRegistry",
    "get_registry",
    "reset_registry",
]
