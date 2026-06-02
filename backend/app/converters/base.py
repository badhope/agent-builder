"""Base converter interface.

A converter takes a single input file and produces a single output
file in ``target_format``. All conversion logic — library calls,
shell-out, multi-step pipelines — happens inside :meth:`BaseConverter.convert`.

Converters must:

* be **stateless and thread-safe** (Celery forks workers).
* declare their supported ``(source_format, target_format)`` edges in ``supports``.
* return a :class:`ConversionResult` describing what happened.
* never raise — failures are encoded in the result.
"""

from __future__ import annotations

import abc
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult, ConversionStatus
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ConversionEdge:
    """A supported source→target conversion edge."""

    source: str
    target: str
    # Quality estimate, 1-5, used for the /v1/formats response
    quality: int = 3
    # Backend identifier (e.g. "libreoffice", "pypandoc")
    backend: str = ""
    # Estimated time in seconds for an average-sized file
    estimated_time_s: float = 5.0


class BaseConverter(abc.ABC):
    """Abstract base class for all converters."""

    # ---- Class-level metadata (override) ----
    name: ClassVar[str] = ""           # short identifier, e.g. "pdf-converter"
    backend: ClassVar[str] = ""        # engine name, e.g. "libreoffice"
    category: ClassVar[str] = "document"

    # ---- Abstract API ----
    @abc.abstractmethod
    def supported_edges(self) -> list[ConversionEdge]:
        """Return the list of supported (source, target) edges."""

    @abc.abstractmethod
    async def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
    ) -> ConversionResult:
        """Perform the conversion.

        Must write the output file into ``output_dir``. The full
        resulting path is reported in :class:`ConversionResult`.
        """

    # ---- Convenience helpers ----
    def supports(self, source: str, target: str) -> bool:
        return any(
            e.source == source.lower() and e.target == target.lower()
            for e in self.supported_edges()
        )

    @contextmanager
    def temp_workdir(self) -> Iterator[Path]:
        """Yield a temporary directory cleaned up on exit."""
        with tempfile.TemporaryDirectory(prefix="dfc-", dir="/tmp") as td:
            yield Path(td)

    def make_output_path(self, output_dir: Path, target_format: str) -> Path:
        """Return a unique output file path inside ``output_dir``."""
        name = f"out-{uuid.uuid4().hex[:12]}.{target_format.lstrip('.')}"
        return output_dir / name

    def _build_result(
        self,
        output_path: Path | None,
        *,
        backend: str,
        started: float,
        error: Exception | None = None,
        steps: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversionResult:
        duration_ms = int((time.monotonic() - started) * 1000)
        if error is None and output_path is not None and output_path.exists():
            size = output_path.stat().st_size
            return ConversionResult(
                status=ConversionStatus.SUCCESS,
                output_path=str(output_path),
                output_bytes_size=size,
                output_mime=None,
                duration_ms=duration_ms,
                backend=backend,
                steps=steps or [],
                metadata=metadata or {},
            )
        return ConversionResult(
            status=ConversionStatus.FAILURE,
            output_path=None,
            output_bytes_size=None,
            output_mime=None,
            duration_ms=duration_ms,
            backend=backend,
            steps=steps or [],
            error_code=getattr(error, "code", "CONVERSION_FAILED"),
            error_message=str(error) if error else "Unknown failure",
            metadata=metadata or {},
        )


__all__ = [
    "BaseConverter",
    "ConversionEdge",
]
