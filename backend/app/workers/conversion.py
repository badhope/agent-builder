"""Conversion worker — invoked by Celery to run a single ``Task``.

The actual conversion logic lives in
:class:`app.services.converter_dispatcher.ConverterDispatcher`. This
module is a thin Celery wrapper that opens its own session, dispatches
the work, and updates the ``Task`` row + emits progress events.
"""

from __future__ import annotations

import asyncio
import uuid

from app.db.models.task import Task, TaskState
from app.db.models.task_log import LogLevel
from app.db.models.user import User
from app.db.models.webhook import WebhookEvent
from app.db.session import get_sessionmaker
from app.logging_config import (
    bind_contextvars,
    clear_contextvars,
    get_logger,
)
from app.services.converter_dispatcher import ConverterDispatcher
from app.services.task_service import TaskService
from app.services.webhook_service import WebhookService
from app.workers.celery_app import celery_app
from app.workers.progress import publish_progress

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.conversion.run_conversion",
    bind=True,
    max_retries=3,
)
def run_conversion(self, task_id: str) -> dict:  # type: ignore[no-untyped-def]
    """Execute the conversion for ``task_id``."""
    bind_contextvars(task_id=task_id, worker_id=str(self.request.id))
    try:
        return asyncio.run(_run(task_id))
    finally:
        clear_contextvars()


async def _run(task_id: str) -> dict:
    sm = get_sessionmaker()
    try:
        tid = uuid.UUID(task_id)
    except (ValueError, TypeError):
        logger.warning("conversion.bad_task_id", task_id=task_id)
        return {"status": "bad_id"}
    async with sm() as session:
        task = await session.get(Task, tid)
        if task is None:
            logger.warning("conversion.task_not_found", task_id=task_id)
            return {"status": "not_found"}
        if task.is_terminal:
            logger.info("conversion.skip_terminal", state=task.state.value)
            return {"status": "skipped", "state": task.state.value}

        # Mark as running
        await TaskService(session).update_state(
            task, TaskState.RUNNING, started=True, queued=False,
            progress_pct=1, progress_message="starting",
        )
        await TaskService(session).increment_attempt(task)
        await session.commit()

    # Run the dispatcher
    dispatcher = ConverterDispatcher()
    user_id_str: str | None = None
    output_payload: dict | None = None
    error_payload: dict | None = None
    try:
        result = await dispatcher.run(task)
    except Exception as exc:
        logger.exception("conversion.exception", error=str(exc))
        async with sm() as session:
            t = await session.get(Task, tid)
            if t is not None:
                await TaskService(session).update_state(
                    t, TaskState.FAILED,
                    error_code="WORKER_EXCEPTION",
                    error_message=str(exc),
                    finished=True,
                )
                user_id_str = str(t.owner_id)
                await session.commit()
        await publish_progress(
            task_id=task_id, user_id=user_id_str,
            payload={"type": "failed", "state": "failed", "progress": 0,
                     "error": {"code": "WORKER_EXCEPTION", "message": str(exc)}},
        )
        return {"status": "failed", "error": str(exc)}

    # Persist outcome
    async with sm() as session:
        t = await session.get(Task, tid)
        if t is None:
            return {"status": "missing"}
        ts = TaskService(session)
        if result.ok and result.output_path:
            from pathlib import Path
            out_path = Path(result.output_path)
            size = out_path.stat().st_size
            sha = _compute_sha256(out_path)
            output_file = await dispatcher._persist_output(
                session, t, out_path, size, sha,
            )
            await ts.update_state(
                t, TaskState.SUCCEEDED,
                output_file_id=output_file.id,
                output_format=out_path.suffix.lstrip(".").lower(),
                output_size=size,
                output_sha256=sha,
                progress_pct=100,
                progress_message="completed",
                finished=True,
                backend=result.backend,
            )
            output_payload = {
                "file_id": str(output_file.id),
                "filename": output_file.filename,
                "size": size,
                "sha256": sha,
            }
        else:
            await ts.update_state(
                t, TaskState.FAILED,
                error_code=result.error_code or "CONVERSION_FAILED",
                error_message=result.error_message or "Unknown failure",
                error_details={"steps": result.steps},
                finished=True,
            )
            error_payload = {
                "code": result.error_code,
                "message": result.error_message,
            }
        await ts.append_log(
            t.id,
            LogLevel.INFO if result.ok else LogLevel.ERROR,
            ("succeeded" if result.ok else "failed") + f" in {result.duration_ms}ms",
            source="worker",
        )
        user_id_str = str(t.owner_id)
        await session.commit()

    # WebSocket progress
    await publish_progress(
        task_id=task_id, user_id=user_id_str,
        payload={
            "type": "completed" if result.ok else "failed",
            "state": "succeeded" if result.ok else "failed",
            "progress": 100 if result.ok else 0,
            "result": output_payload,
            "error": error_payload,
            "duration_ms": result.duration_ms,
        },
    )

    # Webhook dispatch (best-effort)
    try:
        async with sm() as session:
            t = await session.get(Task, tid)
            if t is None:
                return {"status": "done_no_task"}
            user = await session.get(User, t.owner_id)
            if user is None:
                return {"status": "done_no_user"}
            # 1. per-task webhook override
            if t.webhook_url:
                wh = WebhookService(session)
                await wh.enqueue_direct(
                    user=user,
                    url=t.webhook_url,
                    event=(
                        WebhookEvent.TASK_COMPLETED.value
                        if result.ok
                        else WebhookEvent.TASK_FAILED.value
                    ),
                    payload={
                        "task_id": str(t.id),
                        "user_id": str(t.owner_id),
                        "state": t.state.value,
                        "source_format": t.source_format,
                        "target_format": t.target_format,
                        "result": output_payload,
                        "error": error_payload,
                    },
                    secret=t.webhook_secret,
                )
            # 2. global subscription (if any)
            wh = WebhookService(session)
            await wh.enqueue_event(
                user=user,
                event=(
                    WebhookEvent.TASK_COMPLETED
                    if result.ok
                    else WebhookEvent.TASK_FAILED
                ),
                payload={
                    "task_id": str(t.id),
                    "user_id": str(t.owner_id),
                    "state": t.state.value,
                    "source_format": t.source_format,
                    "target_format": t.target_format,
                    "result": output_payload,
                    "error": error_payload,
                },
            )
            await session.commit()
    except Exception as exc:
        logger.warning("conversion.webhook_failed", error=str(exc))

    return {
        "status": "succeeded" if result.ok else "failed",
        "duration_ms": result.duration_ms,
    }


def _compute_sha256(p) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = ["run_conversion"]
