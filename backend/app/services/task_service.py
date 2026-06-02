"""Task service — single-task CRUD + lifecycle for end-users.

This service is consumed by the v1 routes and by the worker. The
``enqueue`` call is implemented in :mod:`app.services.converter_dispatcher`
because it needs to validate the source file and look up converters; this
service provides the read-side and admin/lifecycle helpers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.file import File
from app.db.models.task import Task, TaskState
from app.db.models.task_log import LogLevel, TaskLog
from app.exceptions import NotFoundError, ValidationError


class TaskService:
    """Encapsulates task lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---- read ----

    async def get(self, task_id: uuid.UUID | str) -> Task | None:
        try:
            tid = task_id if isinstance(task_id, uuid.UUID) else uuid.UUID(str(task_id))
        except (ValueError, TypeError):
            return None
        return await self.db.get(Task, tid)

    async def get_or_404(
        self, task_id: uuid.UUID | str, *, user_id: uuid.UUID | str | None = None,
    ) -> Task:
        task = await self.get(task_id)
        if task is None or (
            user_id is not None
            and self._coerce(user_id) != task.owner_id
        ):
            raise NotFoundError("Task not found.", code="TASK_NOT_FOUND")
        return task

    async def get_for_user(
        self, user_id: uuid.UUID | str, task_id: uuid.UUID | str,
    ) -> Task:
        task = await self.get(task_id)
        if task is None or task.owner_id != self._coerce(user_id):
            raise NotFoundError("Task not found.", code="TASK_NOT_FOUND")
        return task

    async def list_for_user(
        self,
        user_id: uuid.UUID | str,
        *,
        limit: int = 50,
        offset: int = 0,
        state: str | TaskState | None = None,
        source_format: str | None = None,
        target_format: str | None = None,
        query: str | None = None,
    ) -> tuple[list[Task], int]:
        uid = self._coerce(user_id)
        stmt = select(Task).where(Task.owner_id == uid)
        count_stmt = select(func.count()).select_from(Task).where(Task.owner_id == uid)
        if state is not None:
            st = state if isinstance(state, TaskState) else TaskState(state)
            stmt = stmt.where(Task.state == st)
            count_stmt = count_stmt.where(Task.state == st)
        if source_format:
            stmt = stmt.where(Task.source_format == source_format.lower())
            count_stmt = count_stmt.where(Task.source_format == source_format.lower())
        if target_format:
            stmt = stmt.where(Task.target_format == target_format.lower())
            count_stmt = count_stmt.where(Task.target_format == target_format.lower())
        if query:
            like = f"%{query.lower()}%"
            cond = or_(
                Task.source_filename.ilike(like),
                Task.id.cast(__import__("sqlalchemy").String).ilike(like),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        stmt = stmt.order_by(desc(Task.created_at)).limit(limit).offset(offset)
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return rows, total

    # ---- logs ----

    async def logs_for_user(
        self, user_id: uuid.UUID | str, task_id: uuid.UUID | str,
        *, limit: int = 200, offset: int = 0,
    ) -> list[TaskLog]:
        task = await self.get_for_user(user_id, task_id)
        stmt = (
            select(TaskLog)
            .where(TaskLog.task_id == task.id)
            .order_by(TaskLog.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def append_log(
        self,
        task_id: uuid.UUID,
        level: LogLevel | int,
        message: str,
        *,
        source: str | None = None,
        worker_id: str | None = None,
        metadata: dict | None = None,
    ) -> TaskLog:
        if isinstance(level, int):
            try:
                level = LogLevel(level)
            except ValueError:
                level = LogLevel.INFO
        entry = TaskLog(
            id=uuid.uuid4(),
            task_id=task_id,
            level=level,
            message=message,
            source=source,
            worker_id=worker_id,
            metadata_json=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    # ---- lifecycle ----

    async def cancel(
        self, user_id: uuid.UUID | str, task_id: uuid.UUID | str,
    ) -> Task:
        task = await self.get_for_user(user_id, task_id)
        if task.is_terminal:
            raise ValidationError(
                "Task is already in a terminal state.",
                code="TASK_NOT_CANCELLABLE",
                details={"state": task.state.value},
            )
        task.state = TaskState.CANCELLED
        task.finished_at = datetime.now(tz=UTC)
        await self.db.flush()
        return task

    async def retry(
        self, user_id: uuid.UUID | str, task_id: uuid.UUID | str,
    ) -> Task:
        task = await self.get_for_user(user_id, task_id)
        if task.state not in {TaskState.FAILED, TaskState.CANCELLED, TaskState.EXPIRED}:
            raise ValidationError(
                "Only failed or cancelled tasks can be retried.",
                code="TASK_NOT_RETRYABLE",
                details={"state": task.state.value},
            )
        if task.attempts >= task.max_attempts:
            raise ValidationError(
                "Maximum attempts exceeded.",
                code="TASK_MAX_ATTEMPTS",
                details={"attempts": task.attempts, "max_attempts": task.max_attempts},
            )
        task.state = TaskState.PENDING
        task.error_code = None
        task.error_message = None
        task.error_details = {}
        task.queued_at = None
        task.started_at = None
        task.finished_at = None
        task.progress_pct = 0
        task.progress_message = "retry requested"
        await self.db.flush()
        return task

    async def delete(
        self, user_id: uuid.UUID | str, task_id: uuid.UUID | str,
    ) -> None:
        task = await self.get_for_user(user_id, task_id)
        # Soft delete: mark the source/output files as deleted; expire the task
        now = datetime.now(tz=UTC)
        task.expires_at = now
        task.finished_at = now
        if task.state not in {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED, TaskState.EXPIRED}:
            task.state = TaskState.EXPIRED
        # Mark source + output files for retention
        await self.db.execute(
            update(File)
            .where(
                or_(
                    File.id == task.source_file_id,
                    File.id == task.output_file_id,
                ),
                File.owner_id == task.owner_id,
                File.deleted_at.is_(None),
            )
            .values(
                deleted_at=now,
                deleted_reason="task_deleted",
            )
        )
        await self.db.flush()

    # ---- worker-facing helpers (low-level) ----

    async def update_state(
        self,
        task: Task,
        new_state: TaskState,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        error_details: dict | None = None,
        output_file_id: uuid.UUID | None = None,
        output_format: str | None = None,
        output_size: int | None = None,
        output_sha256: str | None = None,
        progress_pct: int | None = None,
        progress_message: str | None = None,
        backend: str | None = None,
        started: bool = False,
        finished: bool = False,
        queued: bool = False,
    ) -> Task:
        task.state = new_state
        now = datetime.now(tz=UTC)
        if queued and task.queued_at is None:
            task.queued_at = now
        if started and task.started_at is None:
            task.started_at = now
            if task.queued_at:
                task.queue_time_ms = int((now - task.queued_at).total_seconds() * 1000)
        if finished:
            task.finished_at = now
            if task.started_at:
                task.processing_time_ms = int(
                    (now - task.started_at).total_seconds() * 1000,
                )
        if error_code is not None:
            task.error_code = error_code
        if error_message is not None:
            task.error_message = error_message
        if error_details is not None:
            task.error_details = error_details
        if output_file_id is not None:
            task.output_file_id = output_file_id
        if output_format is not None:
            task.output_format = output_format
        if output_size is not None:
            task.output_size = output_size
        if output_sha256 is not None:
            task.output_sha256 = output_sha256
        if progress_pct is not None:
            task.progress_pct = max(0, min(100, progress_pct))
        if progress_message is not None:
            task.progress_message = progress_message
        if backend is not None:
            task.backend = backend
        await self.db.flush()
        return task

    async def increment_attempt(self, task: Task) -> None:
        task.attempts += 1
        task.last_attempt_at = datetime.now(tz=UTC)
        await self.db.flush()

    async def expire_old(self) -> int:
        """Mark tasks whose retention has elapsed as ``expired``."""
        now = datetime.now(tz=UTC)
        stmt = (
            update(Task)
            .where(
                and_(
                    Task.expires_at < now,
                    Task.state.in_([
                        TaskState.SUCCEEDED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    ]),
                )
            )
            .values(state=TaskState.EXPIRED)
        )
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)

    # ---- internal ----

    @staticmethod
    def _coerce(user_id: uuid.UUID | str) -> uuid.UUID:
        if isinstance(user_id, uuid.UUID):
            return user_id
        return uuid.UUID(str(user_id))


__all__ = ["TaskService"]
