"""LibreOffice headless conversion façade.

LibreOffice is the workhorse for office document conversions. It is
invoked as ``soffice --headless --convert-to <format> --outdir <dir> <file>``.

Caveats
-------
* A user profile dir must be provided or LibreOffice writes to the
  caller's $HOME and locks.
* Two processes cannot share the same profile dir; the worker always
  uses a per-call temp profile (or a pooled one — see :class:`LOProfilePool`).
* We pin the conversion timeout via ``subprocess.run(timeout=...)``.
"""

from __future__ import annotations

import asyncio
import functools
import os
import shutil
import tempfile
import time
from collections.abc import Iterable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.converters.sandbox import SandboxLimits, run_sandboxed
from app.logging_config import get_logger

logger = get_logger(__name__)


LIBREOFFICE_BIN = os.environ.get("LIBREOFFICE_BIN", "soffice")


@functools.lru_cache(maxsize=1)
def is_available() -> bool:
    """Whether the ``soffice`` binary is on PATH.

    Cached so we don't shell out to ``shutil.which`` for every conversion
    task. The PATH is fixed for the lifetime of a worker process.
    """
    return shutil.which(LIBREOFFICE_BIN) is not None


@dataclass(slots=True, frozen=True)
class LOConvertResult:
    output_path: Path
    stderr: str
    returncode: int
    duration_ms: int


def _make_profile_dir() -> Path:
    """Create a fresh, ready-to-use LibreOffice user profile directory."""
    td = Path(tempfile.mkdtemp(prefix="lo-profile-"))
    (td / ".sentinel").write_text("ok")
    return td


def _clean_lock_files(profile: Path) -> None:
    """Remove any leftover `.~lock.*` files from a previous use of the profile."""
    for lock in profile.glob(".~lock.*"):
        try:
            lock.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best-effort
            pass


class LOProfilePool:
    """A small pool of pre-created LibreOffice user profile directories.

    LibreOffice spends 1.5-3s creating and initializing a fresh user
    profile on each cold start; on a 1-page DOCX→PDF where the actual
    conversion is 200ms, that profile initialization is 90% of the
    wall-clock time. Reusing a small set of profiles serializes
    concurrency in exchange for skipping the cold start.

    Lock files (``.~lock.*``) and other transient state are wiped between
    acquisitions so subsequent LibreOffice invocations don't trip on them.

    Usage
    -----
        pool = LOProfilePool(size=4)
        async with pool.acquire() as profile_dir:
            # pass profile_dir to the LO invocation
            ...
    """

    def __init__(self, size: int = 4, base_dir: str | None = None) -> None:
        if size < 1:
            raise ValueError("size must be >= 1")
        self._size = size
        self._base_dir = base_dir
        self._queue: asyncio.Queue[Path] = asyncio.Queue()
        for _ in range(size):
            self._queue.put_nowait(_make_profile_dir())

    @property
    def size(self) -> int:
        return self._size

    @asynccontextmanager
    async def acquire(self, *, timeout_s: float | None = None) -> Iterator[Path]:
        """Acquire a profile; cleaned and returned to the pool on exit."""
        if timeout_s is None:
            profile = await self._queue.get()
        else:
            profile = await asyncio.wait_for(
                self._queue.get(), timeout=timeout_s,
            )
        try:
            _clean_lock_files(profile)
            yield profile
        finally:
            _clean_lock_files(profile)
            # Only return to the pool if the profile is still on disk; if
            # the tempdir was removed out from under us (extremely rare),
            # we replace it with a fresh one.
            if not profile.exists():
                profile = _make_profile_dir()
            self._queue.put_nowait(profile)

    def close(self) -> None:
        """Best-effort cleanup of the pooled profile directories."""
        while not self._queue.empty():
            try:
                p = self._queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover
                break
            shutil.rmtree(p, ignore_errors=True)


# Module-level pool, lazily created on first use.
_profile_pool: LOProfilePool | None = None


def get_profile_pool() -> LOProfilePool:
    """Return the module-level shared profile pool (created on first use)."""
    global _profile_pool
    if _profile_pool is None:
        # Default 4 profiles — matches the default Celery worker concurrency.
        size = int(os.environ.get("LO_PROFILE_POOL_SIZE", "4"))
        _profile_pool = LOProfilePool(size=size)
    return _profile_pool


@contextmanager
def _user_profile():
    """Yield a unique LibreOffice user profile directory, cleaned up on exit."""
    td = _make_profile_dir()
    try:
        yield str(td)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def convert(
    input_path: Path,
    output_dir: Path,
    *,
    target_format: str,
    timeout_s: int = 300,
    extra_args: Iterable[str] = (),
    use_pool: bool = True,
) -> LOConvertResult:
    """Convert ``input_path`` to ``target_format`` via headless LibreOffice.

    The output file is written to ``output_dir`` with the same stem
    as the input and the new extension. Use the returned ``output_path``
    to find it.

    If ``use_pool=True`` (default), a profile is borrowed from the shared
    :func:`get_profile_pool` to skip the cold-start cost. The pool's
    lock files are cleaned before and after each use.
    """
    if not is_available():
        raise RuntimeError(
            "LibreOffice (soffice) is not installed on this host. "
            "Install with `apt install -y libreoffice`."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    pool_cm: asynccontextmanager | None = None
    if use_pool:
        # The pool is async; we adapt by running the async acquire in a
        # short event loop. For Celery workers this is fine because each
        # task already runs in its own asyncio.run.
        profile_path: str | None = None
        try:
            loop = asyncio.new_event_loop()
            try:
                pool = get_profile_pool()
                profile_path = loop.run_until_complete(
                    asyncio.wait_for(pool._queue.get(), timeout=10.0)
                )
                _clean_lock_files(profile_path)
            finally:
                loop.close()
        except Exception as exc:  # noqa: BLE001 - fall back to fresh profile
            logger.warning("lo.pool_unavailable", reason=str(exc))
            profile_path = None
        if profile_path is None:
            return _convert_with_fresh_profile(
                input_path, output_dir,
                target_format=target_format, timeout_s=timeout_s,
                extra_args=extra_args,
            )
        try:
            return _do_lo_convert(
                profile_path, input_path, output_dir,
                target_format=target_format, timeout_s=timeout_s,
                extra_args=extra_args,
            )
        finally:
            _clean_lock_files(profile_path)
            # Return the profile to the pool
            try:
                loop = asyncio.new_event_loop()
                try:
                    pool = get_profile_pool()
                    if not profile_path.exists():
                        profile_path = _make_profile_dir()
                    pool._queue.put_nowait(profile_path)
                finally:
                    loop.close()
            except Exception:  # pragma: no cover
                shutil.rmtree(profile_path, ignore_errors=True)
    return _convert_with_fresh_profile(
        input_path, output_dir,
        target_format=target_format, timeout_s=timeout_s,
        extra_args=extra_args,
    )


def _convert_with_fresh_profile(
    input_path: Path, output_dir: Path,
    *, target_format: str, timeout_s: int, extra_args: Iterable[str],
) -> LOConvertResult:
    with _user_profile() as profile_dir:
        return _do_lo_convert(
            profile_dir, input_path, output_dir,
            target_format=target_format, timeout_s=timeout_s,
            extra_args=extra_args,
        )


def _do_lo_convert(
    profile_dir: str | Path, input_path: Path, output_dir: Path,
    *, target_format: str, timeout_s: int, extra_args: Iterable[str],
) -> LOConvertResult:
    cmd = [
        LIBREOFFICE_BIN,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to",
        target_format,
        "--outdir",
        str(output_dir),
        str(input_path),
        *extra_args,
    ]
    limits = SandboxLimits(
        cpu_seconds=timeout_s + 10,
        address_space_bytes=2 * 1024 * 1024 * 1024,  # 2 GiB
        file_size_bytes=512 * 1024 * 1024,
        timeout_s=timeout_s,
    )
    start = time.monotonic()
    proc = run_sandboxed(
        cmd,
        cwd=output_dir,
        input_path=input_path,
        limits=limits,
        timeout_s=timeout_s,
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    if proc.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed (rc={proc.returncode}): {proc.stderr[:1000]}"
        )

    # LibreOffice writes output as <stem>.<format>
    expected = output_dir / f"{input_path.stem}.{target_format.lstrip('.')}"
    if not expected.exists():
        # Try a case-insensitive match
        candidates = [
            p for p in output_dir.iterdir()
            if p.is_file() and p.suffix.lower() == f".{target_format.lower().lstrip('.')}"
        ]
        if not candidates:
            raise RuntimeError(
                f"LibreOffice did not produce expected output for {input_path.name}"
            )
        expected = candidates[0]

    return LOConvertResult(
        output_path=expected,
        stderr=proc.stderr,
        returncode=proc.returncode,
        duration_ms=duration_ms,
    )


__all__ = [
    "LIBREOFFICE_BIN",
    "LOConvertResult",
    "LOProfilePool",
    "convert",
    "get_profile_pool",
    "is_available",
]
