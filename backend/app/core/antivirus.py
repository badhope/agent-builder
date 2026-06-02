"""Optional ClamAV anti-virus integration.

Provides both a synchronous and an async scanner facade that can be plugged
into upload/ingest code paths. The scanner is fully no-op when
``ANTIVIRUS_ENABLED`` is false; when enabled but the daemon is unreachable
the behaviour is governed by ``ANTIVIRUS_FAIL_OPEN`` (default: allow the
upload but flag it via :class:`ScanResult.error`).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Final

from app.exceptions import AntivirusError
from app.logging_config import get_logger
from app.settings import get_settings

logger = get_logger(__name__)

CHUNK_SIZE: Final[int] = 64 * 1024


# =============================================================================
# Result types
# =============================================================================


@dataclass(slots=True, frozen=True)
class ScanResult:
    """Outcome of an anti-virus scan."""

    clean: bool
    signature: str | None = None
    duration_ms: int = 0
    error: str | None = None
    engine: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "signature": self.signature,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "engine": self.engine,
        }


# =============================================================================
# Scanner
# =============================================================================


class AntivirusScanner:
    """Best-effort ClamAV scanner using ``clamd`` (TCP) when enabled.

    The scanner is intentionally tolerant: a missing dependency, an
    unreachable daemon, or a non-fatal error is logged and translated to
    either a clean result (fail-open) or a hard ``AntivirusError`` (fail-closed)
    based on configuration.
    """

    def __init__(self) -> None:
        cfg = get_settings().antivirus
        self._enabled: bool = bool(cfg.enabled)
        self._host: str = cfg.host
        self._port: int = int(cfg.port)
        self._timeout: int = int(cfg.timeout_s)
        self._fail_open: bool = bool(cfg.fail_open)
        self._client: Any = None
        if self._enabled:
            self._client = self._init_client()

    # -- public -------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def fail_open(self) -> bool:
        return self._fail_open

    def scan_file(self, file_path: str | Path) -> ScanResult:
        """Scan a file on disk. Returns a :class:`ScanResult`."""
        if not self._enabled:
            return ScanResult(clean=True, engine="disabled")

        if self._client is None:
            return self._on_error("scanner not initialised")

        start = time.monotonic()
        try:
            with open(file_path, "rb") as fh:
                raw = self._client.instream(fh)
        except FileNotFoundError:
            return self._on_error(f"file not found: {file_path}")
        except Exception as exc:
            return self._on_error(str(exc))

        duration_ms = int((time.monotonic() - start) * 1000)
        outcome = self._extract_outcome(raw)
        return self._interpret(outcome, duration_ms)

    def scan_bytes(self, payload: bytes) -> ScanResult:
        """Scan an in-memory payload (no disk roundtrip)."""
        if not self._enabled:
            return ScanResult(clean=True, engine="disabled")
        if self._client is None:
            return self._on_error("scanner not initialised")

        start = time.monotonic()
        try:
            import io

            stream: IO[bytes] = io.BytesIO(payload)
            raw = self._client.instream(stream)
        except Exception as exc:
            return self._on_error(str(exc))

        duration_ms = int((time.monotonic() - start) * 1000)
        outcome = self._extract_outcome(raw)
        return self._interpret(outcome, duration_ms)

    async def scan_file_async(self, file_path: str | Path) -> ScanResult:
        """Async wrapper around :meth:`scan_file`."""
        return await asyncio.to_thread(self.scan_file, file_path)

    async def scan_bytes_async(self, payload: bytes) -> ScanResult:
        """Async wrapper around :meth:`scan_bytes`."""
        return await asyncio.to_thread(self.scan_bytes, payload)

    # -- internals ----------------------------------------------------------

    def _init_client(self) -> Any:
        try:
            import clamd  # type: ignore
        except ImportError:
            logger.warning("antivirus.pyclamd_missing")
            return None
        try:
            return clamd.ClamdNetworkSocket(
                host=self._host,
                port=self._port,
                timeout=self._timeout,
            )
        except Exception as exc:
            logger.warning("antivirus.client_init_failed", error=str(exc))
            return None

    def _extract_outcome(self, raw: Any) -> Any:
        if isinstance(raw, dict):
            return raw.get("stream") or raw.get("INSTREAM")
        return raw

    def _interpret(self, outcome: Any, duration_ms: int) -> ScanResult:
        if isinstance(outcome, tuple) and outcome and outcome[0] == "OK":
            return ScanResult(clean=True, duration_ms=duration_ms, engine="clamd")
        signature = (
            outcome[1]
            if isinstance(outcome, tuple) and len(outcome) > 1
            else None
        )
        return ScanResult(
            clean=False,
            signature=signature,
            duration_ms=duration_ms,
            engine="clamd",
        )

    def _on_error(self, msg: str) -> ScanResult:
        if self._fail_open:
            logger.warning("antivirus.fail_open", error=msg)
            return ScanResult(clean=True, error=msg, engine="clamd-error")
        raise AntivirusError(
            "Anti-virus scanner is unavailable.",
            code="ANTIVIRUS_UNAVAILABLE",
            details={"error": msg},
        )


antivirus_scanner = AntivirusScanner()


__all__ = ["AntivirusScanner", "ScanResult", "antivirus_scanner"]
