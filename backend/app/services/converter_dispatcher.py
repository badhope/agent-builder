"""Converter dispatcher — orchestrates the conversion pipeline.

Exposes two entry points consumed by the API and the worker:

* :meth:`ConverterDispatcher.enqueue` — validate, persist a ``Task`` row,
  publish to Celery, and return the new task to the caller.
* :meth:`ConverterDispatcher.enqueue_sync` — like ``enqueue`` but runs
  the conversion inline (suitable for small files / unit tests).

The actual conversion work lives in :meth:`ConverterDispatcher.run`,
which is also called by the Celery task in :mod:`app.workers.conversion`.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.converters.options import ConversionOptions
from app.converters.registry import get_registry
from app.converters.result import ConversionResult, ConversionStatus
from app.core.antivirus import antivirus_scanner
from app.core.sanitizers import sanitize_filename
from app.db.models.file import File, FilePurpose
from app.db.models.task import Task, TaskPriority, TaskState
from app.exceptions import (
    NotFoundError,
    UnsupportedFormatError,
    ValidationError,
)
from app.logging_config import get_logger
from app.services.quota_service import QuotaService
from app.services.storage_service import StorageService
from app.services.task_service import TaskService

logger = get_logger(__name__)


class ConverterDispatcher:
    def __init__(self, storage: StorageService | None = None) -> None:
        self.storage = storage or StorageService()
        self._registry = get_registry()

    # =====================================================================
    # Public API
    # =====================================================================

    async def enqueue(
        self,
        *,
        session: AsyncSession,
        principal: Principal,
        source_file_id: str,
        target_format: str,
        options: dict[str, Any] | None = None,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        priority: str | TaskPriority = TaskPriority.NORMAL,
        idempotency_key: str | None = None,
        batch_id: uuid.UUID | None = None,
        batch_index: int | None = None,
    ) -> Task:
        """Create a Task row + Celery job. Does not run the conversion inline."""
        if not principal.user_id or not principal.user:
            raise ValidationError("Authentication required.", code="AUTH_REQUIRED")
        user = principal.user

        # 1. validate + load source file
        source_file = await self._resolve_source_file(session, user.id, source_file_id)
        source_format = (source_file.format or "").lower()
        target_lc = (target_format or "").lower()
        if not source_format:
            raise UnsupportedFormatError(
                "Source file format could not be determined.",
                code="UNKNOWN_SOURCE_FORMAT",
            )
        # 2. find converter
        entry = self._registry.lookup(source_format, target_lc)
        if entry is None:
            raise UnsupportedFormatError(
                f"Conversion {source_format} → {target_lc} is not supported.",
                code="UNSUPPORTED_CONVERSION",
                details={"source": source_format, "target": target_lc},
            )
        converter, edge = entry
        # 3. quota check
        quota = QuotaService(session)
        await quota.check_can_convert(user)
        await quota.increment_conversion(user)
        # 4. create Task row
        if isinstance(priority, str):
            priority = TaskPriority(priority)
        task = Task(
            id=uuid.uuid4(),
            owner_id=user.id,
            batch_id=batch_id,
            batch_index=batch_index,
            source_file_id=source_file.id,
            source_format=source_format,
            source_filename=source_file.filename,
            target_format=target_lc,
            options_json=options or {},
            state=TaskState.QUEUED,
            priority=priority,
            backend=converter.backend or edge.backend,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
            max_attempts=3,
            queued_at=datetime.now(tz=UTC),
            expires_at=datetime.now(tz=UTC) + timedelta(hours=24),
            idempotency_key=idempotency_key,
        )
        session.add(task)
        await session.flush()
        # 5. dispatch
        try:
            from app.workers.celery_app import celery_app
            celery_app.send_task(
                "app.workers.conversion.run_conversion",
                kwargs={"task_id": str(task.id)},
                queue="conversion",
            )
        except Exception as exc:
            logger.warning("dispatcher.dispatch_failed", error=str(exc))
            # Don't fail the request — the task can be picked up by a sweep
        await session.commit()
        return task

    async def enqueue_sync(
        self,
        *,
        session: AsyncSession,
        principal: Principal,
        source_file_id: str,
        target_format: str,
        options: dict[str, Any] | None = None,
        timeout_s: int = 60,
    ) -> Task:
        """Create the Task row and execute the conversion inline (no Celery)."""
        task = await self.enqueue(
            session=session,
            principal=principal,
            source_file_id=source_file_id,
            target_format=target_format,
            options=options,
        )
        try:
            await asyncio.wait_for(self._run_inline(session, task), timeout=timeout_s)
        except TimeoutError as exc:
            await TaskService(session).update_state(
                task, TaskState.FAILED,
                error_code="CONVERSION_TIMEOUT",
                error_message=f"Inline conversion exceeded {timeout_s}s",
                finished=True,
            )
            await session.commit()
            raise ValidationError(
                "Inline conversion timed out.", code="CONVERSION_TIMEOUT",
            ) from exc
        await session.refresh(task)
        return task

    # =====================================================================
    # Worker entry point
    # =====================================================================

    async def run(self, task: Task) -> ConversionResult:
        """Execute the conversion for ``task`` (Celery worker)."""
        return await self._run_with_logging(task)

    # =====================================================================
    # Internal pipeline
    # =====================================================================

    async def _run_with_logging(self, task: Task) -> ConversionResult:
        _bind = structlog.contextvars.bind_contextvars(
            task_id=str(task.id), user_id=str(task.owner_id),
        )
        try:
            return await self._run(task)
        finally:
            structlog.contextvars.unbind_contextvars("task_id", "user_id")

    async def _run_inline(self, session: AsyncSession, task: Task) -> ConversionResult:
        """Run the conversion pipeline, mutating ``task`` in-place in ``session``."""
        task = await TaskService(session).update_state(
            task, TaskState.RUNNING, started=True, progress_pct=1,
            progress_message="starting", backend=task.backend,
        )
        await session.flush()
        try:
            result = await self._run(task)
        except Exception as exc:
            logger.exception("dispatcher.exception", error=str(exc))
            await TaskService(session).update_state(
                task, TaskState.FAILED,
                error_code="CONVERTER_EXCEPTION",
                error_message=str(exc),
                finished=True,
            )
            await session.commit()
            raise

        if result.ok and result.output_path:
            out_path = Path(result.output_path)
            output_size = out_path.stat().st_size
            output_sha = self._compute_sha256(out_path)
            # Persist the output file
            output_file = await self._persist_output(
                session, task, out_path, output_size, output_sha,
            )
            await TaskService(session).update_state(
                task, TaskState.SUCCEEDED,
                output_file_id=output_file.id,
                output_format=out_path.suffix.lstrip(".").lower(),
                output_size=output_size,
                output_sha256=output_sha,
                progress_pct=100,
                progress_message="completed",
                finished=True,
                backend=result.backend,
            )
        else:
            await TaskService(session).update_state(
                task, TaskState.FAILED,
                error_code=result.error_code or "CONVERSION_FAILED",
                error_message=result.error_message or "Unknown failure",
                error_details={"steps": result.steps},
                finished=True,
            )
        await session.commit()
        return result

    async def _run(self, task: Task) -> ConversionResult:
        """The actual conversion work — no DB access here; pure I/O + compute."""
        started = time.monotonic()
        log = logger.bind(task_id=str(task.id))

        # 1. Anti-virus re-scan of the source (defence in depth)
        if antivirus_scanner.enabled:
            # Pull the first 4 MiB and scan; full scan done at upload time
            try:
                source = await self._get_source_object(task)
                with source.open("rb") as f:
                    head = f.read(4 * 1024 * 1024)
                scan = antivirus_scanner.scan_bytes(head)
                if not scan.clean:
                    return ConversionResult(
                        status=ConversionStatus.FAILURE,
                        backend="antivirus",
                        duration_ms=int((time.monotonic() - started) * 1000),
                        error_code="ANTIVIRUS_REJECTED",
                        error_message=f"Anti-virus rejected: {scan.signature}",
                    )
            except Exception as exc:
                log.warning("dispatcher.av_scan_failed", error=str(exc))

        # 2. Download the source to a tmp dir
        with tempfile.TemporaryDirectory(prefix="dfc-conv-") as td_str:
            tmpdir = Path(td_str)
            try:
                source = await self._get_source_object(task)
            except Exception as exc:
                return ConversionResult(
                    status=ConversionStatus.FAILURE,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error_code="SOURCE_MISSING",
                    error_message=f"Could not fetch source file: {exc}",
                )
            input_path = tmpdir / sanitize_filename(
                source.filename or f"input.{task.source_format}",
                fallback="input",
            )
            try:
                await self.storage.stream_to_file(source.storage_key, input_path)
            except Exception as exc:
                return ConversionResult(
                    status=ConversionStatus.FAILURE,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error_code="STREAM_FAILED",
                    error_message=f"Could not stream source: {exc}",
                )

            # 3. Pick converter
            entry = self._registry.lookup(task.source_format, task.target_format)
            if entry is None:
                return ConversionResult(
                    status=ConversionStatus.FAILURE,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error_code="UNSUPPORTED_CONVERSION",
                    error_message=f"No converter for {task.source_format} → {task.target_format}",
                )
            converter, edge = entry

            # 4. Build options
            opts = ConversionOptions(
                target_format=task.target_format,
                timeout_s=int((task.options_json or {}).get("timeout_s", 300)),
            )
            for k, v in (task.options_json or {}).items():
                if hasattr(opts, k) and k not in {"target_format", "timeout_s"}:
                    setattr(opts, k, v)

            output_dir = tmpdir / "out"
            output_dir.mkdir(parents=True, exist_ok=True)
            log.info(
                "dispatcher.converting",
                source=task.source_format, target=task.target_format,
                backend=converter.backend,
            )
            try:
                result = await converter.convert(input_path, output_dir, opts)
            except Exception as exc:
                log.exception("dispatcher.exception", error=str(exc))
                return ConversionResult(
                    status=ConversionStatus.FAILURE,
                    backend=converter.backend,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error_code="CONVERTER_EXCEPTION",
                    error_message=str(exc),
                )
            if not result.ok or not result.output_path:
                log.warning(
                    "dispatcher.failed",
                    code=result.error_code, error=result.error_message,
                )
                return result
            # Move the output to a stable tmp file outside the context
            out_path = Path(result.output_path)
            final_dir = Path(tempfile.gettempdir()) / f"dfc-out-{uuid.uuid4().hex}"
            final_dir.mkdir(parents=True, exist_ok=True)
            final_path = final_dir / out_path.name
            out_path.rename(final_path)
            result.output_path = str(final_path)
            return result

    # =====================================================================
    # Helpers
    # =====================================================================

    async def _resolve_source_file(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        source_file_id: str,
    ) -> File:
        try:
            fid = uuid.UUID(source_file_id)
        except (ValueError, TypeError) as exc:
            raise NotFoundError("Invalid source file id.", code="FILE_NOT_FOUND") from exc
        file = await session.get(File, fid)
        if file is None or file.deleted_at is not None:
            raise NotFoundError("Source file not found.", code="FILE_NOT_FOUND")
        if file.owner_id != user_id:
            raise NotFoundError("Source file not found.", code="FILE_NOT_FOUND")
        return file

    async def _persist_output(
        self,
        session: AsyncSession,
        task: Task,
        out_path: Path,
        size: int,
        sha: str | None,
    ) -> File:
        output_id = uuid.uuid4()
        target = task.target_format
        filename = (
            Path(task.source_filename).stem
            + "."
            + target.lstrip(".")
        )
        safe_name = sanitize_filename(filename, fallback=f"output.{target}")
        key = self.storage.task_key(
            task.owner_id, task.id, f"{output_id.hex}-{safe_name}",
        )
        await self.storage.put_file(key, out_path, content_type=None)
        file = File(
            id=output_id,
            owner_id=task.owner_id,
            task_id=task.id,
            batch_id=task.batch_id,
            storage_backend=self.storage.backend_name,
            storage_key=key,
            purpose=FilePurpose.OUTPUT,
            filename=safe_name,
            content_type=None,
            size=size,
            sha256=sha,
            format=target,
            scan_status="skipped",
            metadata_json={"generated_by": task.backend or ""},
            expires_at=task.expires_at,
        )
        session.add(file)
        await session.flush()
        return file

    async def _get_source_object(self, task: Task) -> File:
        # Fetch the file metadata (in worker context, this is a fresh session)
        from app.db.session import get_sessionmaker
        sm = get_sessionmaker()
        async with sm() as session:
            file = await session.get(File, task.source_file_id)
            if file is None or file.deleted_at is not None:
                raise NotFoundError("Source file not found.", code="FILE_NOT_FOUND")
            # Detach so caller can use the path
            session.expunge(file)
            return file

    @staticmethod
    def _compute_sha256(p: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


__all__ = ["ConverterDispatcher"]
