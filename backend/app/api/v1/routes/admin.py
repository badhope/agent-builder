"""Admin routes: system stats, user management, queue management, audit logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.db.session import db_session
from app.services.audit_service import AuditService
from app.workers.celery_app import celery_app

router = APIRouter()


@router.get("/stats", dependencies=[Depends(require_admin)])
async def system_stats():
    """High-level health and load metrics."""
    from sqlalchemy import func, select

    from app.db.models.file import File
    from app.db.models.task import Task
    from app.db.models.user import User

    async with db_session() as session:
        total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
        total_tasks = (await session.execute(select(func.count(Task.id)))).scalar_one()
        pending = (
            await session.execute(
                select(func.count(Task.id)).where(Task.state == "pending")
            )
        ).scalar_one()
        running = (
            await session.execute(
                select(func.count(Task.id)).where(Task.state == "running")
            )
        ).scalar_one()
        total_files = (await session.execute(select(func.count(File.id)))).scalar_one()

    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        active = sum(len(v) for v in (inspect.active() or {}).values())
    except Exception:
        active = None

    return {
        "users": total_users,
        "tasks": {"total": total_tasks, "pending": pending, "running": running},
        "files": total_files,
        "workers_active": active,
    }


@router.get("/audit", dependencies=[Depends(require_admin)])
async def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    actor_id: str | None = None,
):
    async with db_session() as session:
        svc = AuditService(session)
        return await svc.list(limit=limit, offset=offset, actor_id=actor_id)


@router.post("/queue/purge", dependencies=[Depends(require_admin)])
async def purge_queue(queue: str = "conversions"):
    """Purge pending tasks from a Celery queue."""
    purged = celery_app.control.purge(queue=queue)
    return {"purged": purged, "queue": queue}


__all__ = ["router"]
