"""User schemas (admin operations and self-service profile updates).

The shared user models (``UserRead``, ``UserUpdate``, ``UserAdminUpdate``)
are defined in :mod:`app.schemas.auth` so the auth and account flows
can share types. This module re-exports them under the user-namespace
so callers can write ``from app.schemas.user import UserRead``.
"""

from __future__ import annotations

from app.schemas.auth import UserAdminUpdate, UserRead, UserUpdate

__all__ = ["UserAdminUpdate", "UserRead", "UserUpdate"]
