"""Batch service — orchestrates the ``Batch`` aggregate.

A batch is a set of conversion tasks submitted together for convenience.
The service is responsible for:

* creating a batch from a list of pre-existing ``Task`` rows;
* listing / fetching batches for a user;
* cancelling, retrying, deleting a batch (cascades to its tasks);
* building a ZIP archive of all successful task outputs.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import UTC, datetime

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.batch_log import BatchLog
from app.db.models.file import File, FilePurpose
from app.db.models.task import Batch, Task, TaskState
from app.exceptions import NotFoundError, ValidationError
from app.services.storage_service import StorageService


class BatchService:
    def __init__(self, db: AsyncSession, storage: StorageService | None = None) -> None:
        self.db = db
        self.storage = storage or StorageService()

    # ---- creation ----

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        tasks: list[Task] | None = None,
        archive_format: str = "zip",
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> Batch:
        tasks = tasks or []
        batch = Batch(
            id=uuid.uuid4(),
            owner_id=owner_id,
            name=name,
            description=description,
            state=TaskState.PENDING if tasks else TaskState.SUCCEEDED,
            total=len(tasks),
            succeeded=0,
            failed=0,
            running=len(tasks),
            archive_format=archive_format,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
        self.db.add(batch)
        await self.db.flush()
        for idx, task in enumerate(tasks):
            task.batch_id = batch.id
            task.batch_index = idx
        await self.db.flush()
        await self.append_log(
            batch.id, "info", "batch.created",
            {"total": batch.total, "name": name},
        )
        return batch

    # ---- listing ----

    async def get_for_user(
        self, user_id: uuid.UUID | str, batch_id: uuid.UUID | str,
    ) -> Batch:
        try:
            bid = batch_id if isinstance(batch_id, uuid.UUID) else uuid.UUID(str(batch_id))
        except (ValueError, TypeError) as exc:
            raise NotFoundError("Batch not found.", code="BATCH_NOT_FOUND") from exc
        batch = await self.db.get(Batch, bid)
        if batch is None or batch.owner_id != self._coerce(user_id):
            raise NotFoundError("Batch not found.", code="BATCH_NOT_FOUND")
        return batch

    async def get_with_items(
        self, user_id: uuid.UUID | str, batch_id: uuid.UUID | str,
    ) -> tuple[Batch, list[Task]]:
        batch = await self.get_for_user(user_id, batch_id)
        stmt = (
            select(Task)
            .where(Task.batch_id == batch.id)
            .order_by(Task.batch_index)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return batch, items

    async def list_for_user(
        self,
        user_id: uuid.UUID | str,
        *,
        limit: int = 50,
        offset: int = 0,
        state: str | TaskState | None = None,
    ) -> tuple[list[Batch], int]:
        uid = self._coerce(user_id)
        stmt = select(Batch).where(Batch.owner_id == uid)
        count_stmt = select(func.count()).select_from(Batch).where(Batch.owner_id == uid)
        if state is not None:
            st = state if isinstance(state, TaskState) else TaskState(state)
            stmt = stmt.where(Batch.state == st)
            count_stmt = count_stmt.where(Batch.state == st)
        stmt = stmt.order_by(desc(Batch.created_at)).limit(limit).offset(offset)
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return rows, total

    # ---- lifecycle ----

    async def cancel(
        self, user_id: uuid.UUID | str, batch_id: uuid.UUID | str,
    ) -> Batch:
        batch = await self.get_for_user(user_id, batch_id)
        if batch.state in {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED, TaskState.EXPIRED}:
            raise ValidationError(
                "Batch is already terminal.",
                code="BATCH_NOT_CANCELLABLE",
                details={"state": batch.state.value},
            )
        batch.state = TaskState.CANCELLED
        batch.finished_at = datetime.now(tz=UTC)
        # Cancel any non-terminal tasks
        await self.db.execute(
            update(Task)
            .where(
                Task.batch_id == batch.id,
                Task.state.in_([TaskState.PENDING, TaskState.QUEUED, TaskState.RUNNING]),
            )
            .values(
                state=TaskState.CANCELLED,
                finished_at=datetime.now(tz=UTC),
            )
        )
        await self.db.flush()
        await self.append_log(batch.id, "info", "batch.cancelled")
        return batch

    async def retry(
        self, user_id: uuid.UUID | str, batch_id: uuid.UUID | str,
    ) -> Batch:
        batch = await self.get_for_user(user_id, batch_id)
        if batch.state not in {TaskState.FAILED, TaskState.CANCELLED, TaskState.EXPIRED}:
            raise ValidationError(
                "Only failed/cancelled batches can be retried.",
                code="BATCH_NOT_RETRYABLE",
                details={"state": batch.state.value},
            )
        # Reset failed tasks to pending
        await self.db.execute(
            update(Task)
            .where(
                Task.batch_id == batch.id,
                Task.state.in_([TaskState.FAILED, TaskState.CANCELLED, TaskState.EXPIRED]),
            )
            .values(
                state=TaskState.PENDING,
                error_code=None,
                error_message=None,
                error_details={},
                queued_at=None,
                started_at=None,
                finished_at=None,
                progress_pct=0,
            )
        )
        batch.state = TaskState.PENDING
        batch.finished_at = None
        await self.db.flush()
        await self.append_log(batch.id, "info", "batch.retry_requested")
        return batch

    async def delete(
        self, user_id: uuid.UUID | str, batch_id: uuid.UUID | str,
    ) -> None:
        batch = await self.get_for_user(user_id, batch_id)
        now = datetime.now(tz=UTC)
        batch.expires_at = now
        batch.finished_at = now
        # Mark all member tasks and their files for retention
        await self.db.execute(
            update(Task)
            .where(Task.batch_id == batch.id)
            .values(
                state=TaskState.EXPIRED,
                finished_at=now,
                expires_at=now,
            )
        )
        await self.db.execute(
            update(File)
            .where(
                File.batch_id == batch.id,
                File.owner_id == batch.owner_id,
                File.deleted_at.is_(None),
            )
            .values(deleted_at=now, deleted_reason="batch_deleted")
        )
        await self.db.flush()

    # ---- recompute counters ----

    async def recompute_counts(self, batch: Batch) -> Batch:
        stmt = (
            select(Task.state, func.count())
            .where(Task.batch_id == batch.id)
            .group_by(Task.state)
        )
        rows = (await self.db.execute(stmt)).all()
        succeeded = failed = running = 0
        for state_value, count in rows:
            count = int(count)
            if state_value == TaskState.SUCCEEDED:
                succeeded = count
            elif state_value == TaskState.FAILED:
                failed = count
            elif state_value in (TaskState.RUNNING, TaskState.QUEUED):
                running += count
        batch.succeeded = succeeded
        batch.failed = failed
        batch.running = running
        # Aggregate state
        total = batch.total
        if succeeded + failed >= total > 0:
            if failed == 0:
                batch.state = TaskState.SUCCEEDED
            elif succeeded == 0:
                batch.state = TaskState.FAILED
            else:
                batch.state = TaskState.SUCCEEDED
            batch.finished_at = datetime.now(tz=UTC)
        elif running > 0:
            batch.state = TaskState.RUNNING
        await self.db.flush()
        return batch

    # ---- archive (ZIP) ----

    async def build_archive(
        self, user_id: uuid.UUID | str, batch_id: uuid.UUID | str,
    ) -> File | None:
        batch, tasks = await self.get_with_items(user_id, batch_id)
        successes = [t for t in tasks if t.state == TaskState.SUCCEEDED and t.output_file_id]
        if not successes:
            return None
        # Build the zip in memory (suitable for tens of MB; we stream large
        # archives separately in the future)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for t in successes:
                file_row = await self.db.get(File, t.output_file_id)
                if file_row is None or file_row.deleted_at is not None:
                    continue
                # Stream the file content into the zip
                try:
                    content = await self.storage.get_file_bytes(file_row)
                except Exception:
                    continue
                # Filename: include the original source name + the right extension
                name = f"{t.batch_index:03d}_{file_row.filename}"
                zf.writestr(name, content)
        data = buf.getvalue()
        archive_file_id = uuid.uuid4()
        archive_key = self.storage.batch_key(
            batch.owner_id, batch.id, f"archive-{archive_file_id.hex}.zip",
        )
        await self.storage.put_bytes(
            archive_key, data,
            content_type="application/zip",
        )
        archive_file = File(
            id=archive_file_id,
            owner_id=batch.owner_id,
            task_id=None,
            batch_id=batch.id,
            storage_backend=self.storage.backend_name,
            storage_key=archive_key,
            purpose=FilePurpose.OUTPUT,
            filename=f"batch-{batch.id.hex[:8]}.zip",
            content_type="application/zip",
            size=len(data),
            sha256=None,
            format="zip",
            scan_status="skipped",
        )
        self.db.add(archive_file)
        await self.db.flush()
        batch.archive_file_id = archive_file.id
        await self.db.flush()
        await self.append_log(
            batch.id, "info", "batch.archive_built",
            {"file_id": str(archive_file.id), "size": len(data)},
        )
        return archive_file

    # ---- logs ----

    async def logs_for_user(
        self, user_id: uuid.UUID | str, batch_id: uuid.UUID | str,
    ) -> list[BatchLog]:
        batch = await self.get_for_user(user_id, batch_id)
        stmt = select(BatchLog).where(BatchLog.batch_id == batch.id).order_by(BatchLog.created_at)
        return list((await self.db.execute(stmt)).scalars().all())

    async def append_log(
        self,
        batch_id: uuid.UUID,
        level: str,
        event: str,
        metadata: dict | None = None,
    ) -> BatchLog:
        entry = BatchLog(
            id=uuid.uuid4(),
            batch_id=batch_id,
            level=level,
            event=event,
            metadata_json=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    @staticmethod
    def _coerce(user_id: uuid.UUID | str) -> uuid.UUID:
        if isinstance(user_id, uuid.UUID):
            return user_id
        return uuid.UUID(str(user_id))


__all__ = ["BatchService"]
