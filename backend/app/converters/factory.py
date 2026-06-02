"""Converter factory: given source + target, return a converter instance.

This is the public entry point used by the worker / dispatch layer.
"""

from __future__ import annotations

from app.converters.base import BaseConverter, ConversionEdge
from app.converters.registry import get_registry
from app.exceptions import UnsupportedFormatError
from app.logging_config import get_logger

logger = get_logger(__name__)


def pick_converter(source: str, target: str) -> tuple[BaseConverter, ConversionEdge]:
    """Find a converter that can handle ``source → target``.

    Raises :class:`UnsupportedFormatError` if none is registered.
    """
    registry = get_registry()
    result = registry.lookup(source, target)
    if result is None:
        supported = ", ".join(
            f"{e.source}→{e.target}" for e in registry.all_edges()
        )
        raise UnsupportedFormatError(
            f"Conversion {source}→{target} is not supported.",
            code="UNSUPPORTED_CONVERSION",
            details={
                "source": source,
                "target": target,
                "supported_count": len(registry.all_edges()),
                "example_supported": supported[:500],
            },
        )
    return result


__all__ = ["pick_converter"]
