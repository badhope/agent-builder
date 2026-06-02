"""Conversion options passed to converters.

These are deliberately backend-agnostic: a converter implementation
translates them into engine-specific flags. New options should be
optional and have safe defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.converters.result import ConversionQuality


@dataclass(slots=True)
class ConversionOptions:
    """Tunable parameters for a conversion."""

    target_format: str
    quality: ConversionQuality = ConversionQuality.HIGH
    preserve_metadata: bool = True
    compress_output: bool = False
    ocr: bool = False
    ocr_language: str = "eng"
    page_range: str | None = None       # "1-10" or "1,3,5"
    password: str | None = None
    timeout_s: int = 300
    cpu_limit: int = 2
    memory_limit_mb: int = 1024
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_format": self.target_format,
            "quality": self.quality.value,
            "preserve_metadata": self.preserve_metadata,
            "compress_output": self.compress_output,
            "ocr": self.ocr,
            "ocr_language": self.ocr_language,
            "page_range": self.page_range,
            "password": "***" if self.password else None,
            "timeout_s": self.timeout_s,
            "cpu_limit": self.cpu_limit,
            "memory_limit_mb": self.memory_limit_mb,
            "custom": self.custom,
        }


__all__ = ["ConversionOptions"]
