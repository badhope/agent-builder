"""File sanitizers."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

# Reserved Windows device names
_RESERVED_WIN = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# Allowed characters in a stored filename. Conservative: letters, digits,
# dot, dash, underscore, space. Everything else is replaced with ``_``.
_SAFE_RE = re.compile(r"[^A-Za-z0-9._\- ]")


class PathTraversalError(ValueError):
    """Raised when a path is found to traverse outside the allowed root."""


def sanitize_filename(name: str, *, fallback: str = "untitled", max_len: int = 255) -> str:
    """Return a safe storage filename with the original extension preserved."""
    if not name:
        return fallback

    p = PurePosixPath(name.replace("\\", "/"))
    base = p.name
    if not base or base in {".", ".."}:
        return fallback

    # Split stem + ext
    if "." in base:
        stem, _, ext = base.rpartition(".")
        if not stem:
            stem = ext
            ext = ""
    else:
        stem, ext = base, ""

    stem = _SAFE_RE.sub("_", stem).strip("._- ")
    if not stem:
        stem = fallback
    ext = _SAFE_RE.sub("", ext).lower()

    # Disallow reserved Windows device names
    if stem.lower().split(".")[0] in _RESERVED_WIN:
        stem = f"_{stem}"

    out = f"{stem}.{ext}" if ext else stem
    if len(out) > max_len:
        # Truncate stem
        keep = max_len - len(ext) - 1 if ext else max_len
        out = (stem[:keep] + ("." + ext if ext else ""))
    return out


def extension_of(filename: str | None) -> str:
    if not filename:
        return ""
    return PurePosixPath(filename).suffix.lstrip(".").lower()


def safe_join(root: str, *parts: str) -> Path:
    """Join ``parts`` under ``root`` and reject any traversal attempt.

    Raises ``PathTraversalError`` if the resolved path escapes ``root``.
    """
    root_path = Path(root).resolve()
    candidate = root_path.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise PathTraversalError(
            f"Path {candidate} escapes the root {root_path}",
        ) from exc
    return candidate


__all__ = ["PathTraversalError", "extension_of", "safe_join", "sanitize_filename"]
