"""WeasyPrint façade for HTML → PDF (canonical location).

The legacy ``weasyprint_backend`` import path is preserved as a shim.
"""

from __future__ import annotations

import functools
from pathlib import Path


@functools.lru_cache(maxsize=1)
def is_available() -> bool:
    """Whether WeasyPrint is importable. Cached per process."""
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


def html_to_pdf(input_path: Path, output_path: Path) -> None:
    """Render ``input_path`` (HTML) to ``output_path`` (PDF) via WeasyPrint."""
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError("WeasyPrint is not installed.") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=str(input_path)).write_pdf(target=str(output_path))


__all__ = ["html_to_pdf", "is_available"]
