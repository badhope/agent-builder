"""Pytest fixtures shared across the test suite."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force the test env before importing the app
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-for-pytest-only-1234567890")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://docconv:docconv@localhost:5432/docconv",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("JWT_KEYS_DIR", "/tmp/jwt-test-keys")
os.environ.setdefault("STORAGE_LOCAL_ROOT", "/tmp/docconv-test-storage")

# Ensure the JWT keys exist (so security module boots).
from app.core import security as _security  # noqa: E402
from app.scripts import generate_jwt_keys  # noqa: E402

try:
    generate_jwt_keys.main()
except SystemExit:
    pass

from app.db import models  # noqa: E402,F401  -- ensure models are registered
from app.db.session import dispose_engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.WindowsProactorEventLoopPolicy() if os.name == "nt" else asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture
async def app_instance():
    app = create_app()
    yield app
    await dispose_engine()


@pytest_asyncio.fixture
async def client(app_instance) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    from app.db.session import get_engine

    engine = get_engine()
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> Any:
    from app.services.user_service import UserService
    from app.db.models.user import UserPlan

    svc = UserService(db_session)
    email = f"test+{uuid.uuid4().hex[:8]}@example.com"
    user = await svc.create(
        email=email,
        password="Sup3rStrong!Pass",
        is_admin=True,
        plan=UserPlan.ENTERPRISE,
    )
    return user


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user) -> dict[str, str]:
    r = await client.post(
        "/v1/auth/login",
        json={"email": test_user.email, "password": "Sup3rStrong!Pass"},
    )
    r.raise_for_status()
    tokens = r.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
