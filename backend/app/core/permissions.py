"""Permissions and roles for API keys / users."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ANON = "anon"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class Permission(StrEnum):
    # Files
    FILES_READ = "files:read"
    FILES_WRITE = "files:write"
    FILES_DELETE = "files:delete"
    # Conversion
    CONVERT_READ = "convert:read"
    CONVERT_WRITE = "convert:write"
    CONVERT_DELETE = "convert:delete"
    # Batches
    BATCHES_READ = "batches:read"
    BATCHES_WRITE = "batches:write"
    BATCHES_DELETE = "batches:delete"
    # Tasks
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    TASKS_DELETE = "tasks:delete"
    # Webhooks
    WEBHOOKS_READ = "webhooks:read"
    WEBHOOKS_WRITE = "webhooks:write"
    # API keys (self)
    APIKEYS_READ = "apikeys:read"
    APIKEYS_WRITE = "apikeys:write"
    # 2FA (self)
    TOTP_WRITE = "totp:write"
    ACCOUNT_READ = "account:read"
    ACCOUNT_WRITE = "account:write"
    # Admin
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_USERS = "admin:users"
    ADMIN_QUEUE = "admin:queue"
    ADMIN_AUDIT = "admin:audit"


USER_PERMISSIONS: frozenset[Permission] = frozenset({
    Permission.FILES_READ, Permission.FILES_WRITE, Permission.FILES_DELETE,
    Permission.CONVERT_READ, Permission.CONVERT_WRITE, Permission.CONVERT_DELETE,
    Permission.BATCHES_READ, Permission.BATCHES_WRITE, Permission.BATCHES_DELETE,
    Permission.TASKS_READ, Permission.TASKS_WRITE, Permission.TASKS_DELETE,
    Permission.WEBHOOKS_READ, Permission.WEBHOOKS_WRITE,
    Permission.APIKEYS_READ, Permission.APIKEYS_WRITE,
    Permission.TOTP_WRITE,
    Permission.ACCOUNT_READ, Permission.ACCOUNT_WRITE,
})

MODERATOR_PERMISSIONS: frozenset[Permission] = USER_PERMISSIONS | frozenset({
    Permission.ADMIN_READ,
})

ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(set(Permission))


def role_for_user(*, is_admin: bool, is_active: bool = True) -> Role:
    if not is_active:
        return Role.ANON
    if is_admin:
        return Role.ADMIN
    return Role.USER


def default_permissions_for(role: Role) -> frozenset[Permission]:
    if role == Role.ADMIN:
        return ADMIN_PERMISSIONS
    if role == Role.MODERATOR:
        return MODERATOR_PERMISSIONS
    if role == Role.USER:
        return USER_PERMISSIONS
    return frozenset()


__all__ = [
    "ADMIN_PERMISSIONS",
    "MODERATOR_PERMISSIONS",
    "USER_PERMISSIONS",
    "Permission",
    "Role",
    "default_permissions_for",
    "role_for_user",
]
