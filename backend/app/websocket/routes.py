"""WebSocket routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import jwt_manager
from app.db.session import db_session
from app.db.models.task import Task
from app.exceptions import AuthenticationError
from app.logging_config import bind_contextvars, clear_contextvars, get_logger
from app.websocket.manager import manager

logger = get_logger(__name__)

router = APIRouter()


async def _authenticate_websocket(
    websocket: WebSocket, token: str | None,
) -> tuple[uuid.UUID | None, str | None]:
    """Authenticate a WebSocket connection from a JWT or API key.

    Returns ``(user_id, error)`` — at most one is set.
    """
    if not token:
        return None, "missing_token"
    try:
        # Try JWT
        if token.count(".") == 2:
            claims = jwt_manager.verify_token(token, expected_type="access")
            return uuid.UUID(claims["sub"]), None
    except AuthenticationError as exc:
        return None, exc.code

    # API Key not directly supported in WS; clients should use JWT
    return None, "unsupported_token"


async def _authorize_task_access(
    task_id: uuid.UUID, user_id: uuid.UUID, *,
    is_admin: bool = False,
) -> tuple[bool, str | None]:
    """Verify that ``user_id`` may subscribe to ``task_id`` progress events.

    SECURITY: Without this check, any authenticated user can listen to any
    other user's task progress (CWE-639 IDOR). An admin can subscribe to
    any task for support purposes.
    """
    async with db_session() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return False, "task_not_found"
        if is_admin:
            return True, None
        if task.owner_id != user_id:
            return False, "forbidden"
        return True, None


@router.websocket("/ws/tasks/{task_id}")
async def task_progress_ws(
    websocket: WebSocket,
    task_id: str,
    token: str | None = Query(default=None),
) -> None:
    user_id, err = await _authenticate_websocket(websocket, token)
    if err:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=err)
        return

    try:
        tid = uuid.UUID(task_id)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="bad_task_id")
        return

    # SECURITY: IDOR check — refuse subscriptions to tasks the user doesn't own.
    authorized, reason = await _authorize_task_access(tid, user_id)
    if not authorized:
        logger.warning(
            "ws.task_access_denied",
            task_id=str(tid),
            user_id=str(user_id),
            reason=reason,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason or "forbidden")
        return

    bind_contextvars(task_id=str(tid), user_id=str(user_id) if user_id else None)
    await manager.connect(websocket, str(tid), user_id)
    try:
        # Send a hello so the client knows it's connected
        await websocket.send_json(
            {"type": "hello", "task_id": str(tid), "user_id": str(user_id) if user_id else None}
        )
        while True:
            # We don't expect any inbound messages other than pings;
            # receive_text is used to detect disconnects.
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket, str(tid), user_id)
        clear_contextvars()


__all__ = ["router"]
