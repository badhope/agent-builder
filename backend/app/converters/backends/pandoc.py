"""Pandoc façade.

Used for markup ↔ document conversions. Pandoc is fast, high-quality
for prose documents, and supports an enormous range of formats.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from app.converters.sandbox import SandboxLimits, run_sandboxed
from app.logging_config import get_logger

logger = get_logger(__name__)


PANDOC_BIN = os.environ.get("PANDOC_BIN", "pandoc")


def is_available() -> bool:
    return shutil.which(PANDOC_BIN) is not None


@dataclass(slots=True, frozen=True)
class PandocResult:
    output_path: Path
    stderr: str
    returncode: int
    duration_ms: int


def convert(
    input_path: Path,
    output_path: Path,
    *,
    from_format: str | None = None,
    to_format: str | None = None,
    extra_args: list[str] | None = None,
    timeout_s: int = 120,
) -> PandocResult:
    """Convert via pandoc.

    ``from_format`` / ``to_format`` are optional — pandoc can infer
    from file extensions in most cases.
    """
    if not is_available():
        raise RuntimeError("pandoc is not installed on this host.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [PANDOC_BIN, str(input_path), "-o", str(output_path)]
    if from_format:
        cmd[1:1] = [f"-f{from_format}" if not from_format.startswith("-") else from_format]
    if to_format:
        cmd[1:1] = [f"-t{to_format}" if not to_format.startswith("-") else to_format]
    if extra_args:
        cmd.extend(extra_args)

    limits = SandboxLimits(
        cpu_seconds=timeout_s + 10,
        address_space_bytes=512 * 1024 * 1024,
        file_size_bytes=128 * 1024 * 1024,
        timeout_s=timeout_s,
    )
    start = time.monotonic()
    proc = run_sandboxed(
        cmd,
        cwd=output_path.parent,
        input_path=input_path,
        limits=limits,
        timeout_s=timeout_s,
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    if proc.returncode != 0:
        raise RuntimeError(
            f"pandoc failed (rc={proc.returncode}): {proc.stderr[:1000]}"
        )

    return PandocResult(
        output_path=output_path,
        stderr=proc.stderr,
        returncode=proc.returncode,
        duration_ms=duration_ms,
    )


__all__ = ["PANDOC_BIN", "PandocResult", "convert", "is_available"]
