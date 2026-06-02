"""Storage layer tests (local backend)."""

from __future__ import annotations

import io
import uuid

import pytest

from app.settings import get_settings


@pytest.fixture
def local_root(tmp_path):
    s = get_settings()
    s.storage.local_root = str(tmp_path)
    s.storage.backend = "local"
    return str(tmp_path)


@pytest.mark.asyncio
async def test_local_storage_round_trip(local_root):
    from app.storage.factory import build_storage

    storage = build_storage()
    key = f"test/{uuid.uuid4().hex}.txt"
    data = b"hello world"
    await storage.put_bytes(key, data, content_type="text/plain")
    obj = await storage.stat(key)
    assert obj is not None
    assert obj.size == len(data)
    assert obj.content_type == "text/plain"

    out = await storage.get_bytes(key)
    assert out == data

    buf = io.BytesIO()
    async for chunk in storage.stream(key):
        buf.write(chunk)
    buf.seek(0)
    assert buf.read() == data

    listed = await storage.list_keys("test/")
    assert any(o == key for o in listed)

    assert await storage.delete(key) is True
    assert await storage.stat(key) is None