"""Converter package init.

Re-exports the public API for the conversion engine.
"""

from app.converters.base import BaseConverter, ConversionEdge
from app.converters.factory import pick_converter
from app.converters.options import ConversionOptions
from app.converters.registry import (
    ConverterRegistry,
    get_registry,
    reset_registry,
)
from app.converters.result import ConversionQuality, ConversionResult, ConversionStatus

__all__ = [
    "BaseConverter",
    "ConversionEdge",
    "ConversionOptions",
    "ConversionQuality",
    "ConversionResult",
    "ConversionStatus",
    "ConverterRegistry",
    "get_registry",
    "pick_converter",
    "reset_registry",
]
