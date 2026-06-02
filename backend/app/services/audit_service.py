"""Audit log service — best-effort writes, never raises into the request.

The middleware inserts records directly; the service is used by
business-logic helpers (e.g. login flow) and by the admin audit endpoint.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.logging_config import get_logger

logger = get_logger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        *,
        user_id: uuid.UUID | None,
        action: str,
        api_key_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Append a new audit log entry. Never raises into the caller."""
        try:
            entry = AuditLog(
                id=uuid.uuid4(),
                actor_id=user_id,
                actor_api_key_id=api_key_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                success=success,
                error_message=error_message,
            )
            self.db.add(entry)
            await self.db.commit()
        except Exception as exc:
            logger.warning("audit.write_failed", error=str(exc), action=action)
            try:
                await self.db.rollback()
            except Exception:
                pass

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at))
        count_stmt = select(func.count()).select_from(AuditLog)
        if actor_id:
            try:
                actor_uuid = uuid.UUID(actor_id)
            except ValueError:
                actor_uuid = None
            if actor_uuid is not None:
                stmt = stmt.where(AuditLog.actor_id == actor_uuid)
                count_stmt = count_stmt.where(AuditLog.actor_id == actor_uuid)
        if action:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
            count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
            count_stmt = count_stmt.where(AuditLog.resource_id == resource_id)
        stmt = stmt.limit(limit).offset(offset)
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return rows, total


__all__ = ["AuditService"]
