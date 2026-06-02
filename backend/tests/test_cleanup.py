"""Tests for cleanup workers (purge logic)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_purge_does_not_hard_delete_user_requested_soft_deleted_files():
    """User-requested soft deletes must remain in DB during their grace period.

    Bug: _purge_expired_files used to delete ALL rows with deleted_at IS NOT NULL,
    wiping user-requested soft deletes that should still be restorable.
    """
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from sqlalchemy import select

    from app.db.models.file import File, FilePurpose, FileScanStatus
    from app.db.models.user import User
    from app.db.session import get_sessionmaker
    from app.workers.cleanup import _purge_expired_files

    sm = get_sessionmaker()
    user_id = uuid4()

    async with sm() as session:
        user = User(
            id=user_id,
            email=f"purgetest-{user_id.hex[:8]}@example.com",
            email_lower=f"purgetest-{user_id.hex[:8]}@example.com",
            password_hash="x" * 60,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        # File 1: user-requested soft delete, recent — must be kept
        recent = File(
            id=uuid4(),
            owner_id=user_id,
            storage_key=f"u/{user_id.hex}/recent.pdf",
            purpose=FilePurpose.SOURCE.value,
            filename="recent.pdf",
            size=100,
            scan_status=FileScanStatus.SKIPPED.value,
            expires_at=datetime.now(tz=UTC) + timedelta(days=30),
            deleted_at=datetime.now(tz=UTC) - timedelta(hours=1),
            deleted_reason="user_requested",
        )
        # File 2: retention-elapsed soft delete — must be hard-deleted
        expired = File(
            id=uuid4(),
            owner_id=user_id,
            storage_key=f"u/{user_id.hex}/expired.pdf",
            purpose=FilePurpose.SOURCE.value,
            filename="expired.pdf",
            size=100,
            scan_status=FileScanStatus.SKIPPED.value,
            expires_at=datetime.now(tz=UTC) - timedelta(days=1),
            deleted_at=None,
        )
        session.add_all([recent, expired])
        await session.commit()

    await _purge_expired_files()

    async with sm() as session:
        rows = (await session.execute(
            select(File).where(File.owner_id == user_id)
        )).scalars().all()
        keys = {r.storage_key for r in rows}

    assert f"u/{user_id.hex}/recent.pdf" in keys, \
        "User-requested soft delete must NOT be hard-deleted"
    assert f"u/{user_id.hex}/expired.pdf" not in keys, \
        "Retention-elapsed file should be soft- AND hard-deleted"


async def test_purge_hard_deletes_old_user_requested_after_grace_period():
    """After grace period, even user-requested deletes should be hard-deleted."""
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from sqlalchemy import select

    from app.db.models.file import File, FilePurpose, FileScanStatus
    from app.db.models.user import User
    from app.db.session import get_sessionmaker
    from app.workers.cleanup import _purge_expired_files

    sm = get_sessionmaker()
    user_id = uuid4()

    async with sm() as session:
        user = User(
            id=user_id,
            email=f"purgetest2-{user_id.hex[:8]}@example.com",
            email_lower=f"purgetest2-{user_id.hex[:8]}@example.com",
            password_hash="x" * 60,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        # Soft-deleted long ago — past grace period
        old = File(
            id=uuid4(),
            owner_id=user_id,
            storage_key=f"u/{user_id.hex}/old.pdf",
            purpose=FilePurpose.SOURCE.value,
            filename="old.pdf",
            size=100,
            scan_status=FileScanStatus.SKIPPED.value,
            expires_at=datetime.now(tz=UTC) - timedelta(days=1),
            deleted_at=datetime.now(tz=UTC) - timedelta(days=30),
            deleted_reason="user_requested",
        )
        session.add(old)
        await session.commit()

    await _purge_expired_files()

    async with sm() as session:
        rows = (await session.execute(
            select(File).where(File.storage_key == f"u/{user_id.hex}/old.pdf")
        )).scalars().all()
        assert rows == [], "Past-grace-period files should be hard-deleted"
