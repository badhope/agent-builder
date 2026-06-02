"""Tesseract OCR façade."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from app.converters.sandbox import SandboxLimits, run_sandboxed

TESSERACT_BIN = os.environ.get("TESSERACT_BIN", "tesseract")


def is_available() -> bool:
    return shutil.which(TESSERACT_BIN) is not None


def image_to_text(
    input_path: Path,
    output_path: Path,
    *,
    language: str = "eng",
    timeout_s: int = 120,
) -> None:
    """Run Tesseract OCR on ``input_path`` writing text to ``output_path``."""
    if not is_available():
        raise RuntimeError("tesseract is not installed on this host.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        TESSERACT_BIN,
        str(input_path),
        str(output_path.with_suffix("")),  # tesseract appends .txt
        "-l",
        language,
    ]
    limits = SandboxLimits(
        cpu_seconds=timeout_s + 10,
        address_space_bytes=512 * 1024 * 1024,
        file_size_bytes=64 * 1024 * 1024,
        timeout_s=timeout_s,
    )
    _start = time.monotonic()
    proc = run_sandboxed(cmd, limits=limits, timeout_s=timeout_s)
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract failed: {proc.stderr[:500]}")


__all__ = ["TESSERACT_BIN", "image_to_text", "is_available"]
