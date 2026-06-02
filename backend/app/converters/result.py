"""Conversion engine: data types and result envelope."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ConversionQuality(StrEnum):
    """Quality level hint passed to backends."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LOSSLESS = "lossless"


class ConversionStatus(StrEnum):
    """Final status of a conversion attempt."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


@dataclass(slots=True, frozen=True)
class ConversionResult:
    """The outcome of a single conversion attempt."""

    status: ConversionStatus
    output_path: str | None = None        # absolute path inside tmp sandbox
    output_bytes_size: int | None = None
    output_mime: str | None = None
    duration_ms: int = 0
    backend: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == ConversionStatus.SUCCESS and self.output_path is not None


__all__ = [
    "ConversionQuality",
    "ConversionResult",
    "ConversionStatus",
]
