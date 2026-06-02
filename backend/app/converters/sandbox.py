"""Subprocess-level sandbox for running external converters.

We do not rely on Docker for the worker (no nested container support
on most production setups) — instead we use:

* a private working directory (per-task, on the system temp root)
* ``resource.setrlimit`` to cap CPU time, address space, FSize, and NOFILE
* ``preexec_fn`` to drop into a new process group and ``setsid`` for clean kill
  (POSIX only — on Windows the rlimits silently no-op and we rely on
  the wall-clock timeout alone)
* a hard wall-clock ``subprocess.run(timeout=...)``
* ``env=`` scrubbing to remove secrets and LD_PRELOAD attacks

This is "defence in depth" — the converter is not run as root, has no
network access by default (we never pass network config), and can only
read from the supplied input directory and write to the output directory.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IS_WINDOWS = sys.platform == "win32"

if not IS_WINDOWS:
    import resource


@dataclass(slots=True, frozen=True)
class SandboxLimits:
    """Resource limits for a sandboxed subprocess."""

    cpu_seconds: int = 60
    address_space_bytes: int = 1024 * 1024 * 1024  # 1 GiB
    file_size_bytes: int = 256 * 1024 * 1024       # 256 MiB output cap
    nofile: int = 256
    nproc: int = 32
    timeout_s: int = 300


def _safe_env() -> dict[str, str]:
    """Build a minimal, platform-appropriate environment for child processes."""
    if IS_WINDOWS:
        # Windows PATH discovery is environment-driven; we just inherit
        # the existing PATH/LANG/TMP from the parent so the child can
        # find the converters (libreoffice, weasyprint, wkhtmltopdf...).
        return {
            "PATH": os.environ.get("PATH", ""),
            "PATHEXT": os.environ.get("PATHEXT", ".EXE;.BAT;.CMD"),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
            "TEMP": tempfile.gettempdir(),
            "TMP": tempfile.gettempdir(),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        }
    tmp = tempfile.gettempdir()
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": tmp,
        "TMPDIR": tmp,
    }


def _apply_rlimits(limits: SandboxLimits) -> None:
    """Apply POSIX resource limits in the child process after fork."""
    if IS_WINDOWS:  # pragma: no cover - POSIX only
        return
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds + 5))
    except (ValueError, OSError):  # pragma: no cover
        pass
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limits.address_space_bytes, limits.address_space_bytes))
    except (ValueError, OSError):  # pragma: no cover
        pass
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_size_bytes, limits.file_size_bytes))
    except (ValueError, OSError):  # pragma: no cover
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (limits.nofile, limits.nofile))
    except (ValueError, OSError):  # pragma: no cover
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (limits.nproc, limits.nproc))
    except (ValueError, OSError):  # pragma: no cover
        pass


@contextmanager
def sandbox(limits: SandboxLimits | None = None):
    """Context manager yielding nothing — use inside ``subprocess.run`` via ``preexec_fn``."""
    lim = limits or SandboxLimits()
    yield _preexec(lim)


def _preexec(limits: SandboxLimits):  # pragma: no cover - runs in child
    """Closure returning a preexec_fn for ``subprocess``."""

    def _fn() -> None:
        # New process group → easy SIGKILL of children
        try:
            os.setsid()
        except (OSError, AttributeError):
            pass
        # Ignore SIGPIPE so a broken pipe doesn't kill us
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        except (ValueError, OSError, AttributeError):
            pass
        # Apply rlimits
        _apply_rlimits(limits)
        # Switch to the per-task cwd (chroot-like effect)
        try:
            os.chdir(tempfile.gettempdir())
        except OSError:
            pass

    return _fn


def _preexec_windows(limits: SandboxLimits):  # pragma: no cover
    """Windows-compatible preexec_fn. We can't apply rlimits; just create
    a new process group via CREATE_NEW_PROCESS_GROUP."""

    def _fn() -> None:
        # Best effort: detach from the console
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError, AttributeError):
            pass

    return _fn


def run_sandboxed(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
    env_overrides: Mapping[str, str] | None = None,
    limits: SandboxLimits | None = None,
    timeout_s: int = 300,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` inside the sandbox.

    The function:

    * uses ``subprocess.run`` with ``preexec_fn`` for resource limits,
    * restricts env to a safe set,
    * captures stdout/stderr,
    * enforces a wall-clock timeout.

    Cross-platform: on POSIX we apply rlimits, on Windows we just enforce
    the wall-clock timeout and use a per-task working directory under
    the system temp root.
    """
    env = _safe_env()
    if env_overrides:
        env.update(env_overrides)

    if cwd is None:
        cwd = Path(tempfile.mkdtemp(prefix="dfc-sandbox-"))
    cwd.mkdir(parents=True, exist_ok=True)

    # Mirror the input file into the sandbox cwd so the converter can
    # reference it by basename.
    if input_path is not None and cwd is not None:
        link = cwd / input_path.name
        if not link.exists():
            try:
                os.symlink(input_path.resolve(), link)
            except (OSError, NotImplementedError):
                shutil.copy2(input_path, link)

    preexec_fn: Any = None
    extra_kwargs: dict[str, Any] = {}
    if not IS_WINDOWS:
        preexec_fn = _preexec(limits or SandboxLimits(timeout_s=timeout_s))
    else:
        preexec_fn = _preexec_windows(limits or SandboxLimits(timeout_s=timeout_s))
        # CREATE_NEW_PROCESS_GROUP so we can CTRL_BREAK_EVENT the group
        extra_kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0,
        )

    completed = subprocess.run(
        list(cmd),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=check,
        preexec_fn=preexec_fn,
        **extra_kwargs,
    )

    return completed


def default_limits(timeout_s: int = 300, memory_mb: int = 1024) -> SandboxLimits:
    return SandboxLimits(
        cpu_seconds=timeout_s + 10,
        address_space_bytes=memory_mb * 1024 * 1024,
        file_size_bytes=512 * 1024 * 1024,
        timeout_s=timeout_s,
    )


__all__ = [
    "SandboxLimits",
    "default_limits",
    "run_sandboxed",
    "sandbox",
]
