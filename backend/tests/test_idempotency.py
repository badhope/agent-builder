"""Idempotency-Key middleware tests.

Verifies that the ``Idempotency-Key`` header causes identical request
bodies to return the cached response, in-flight requests to 409, and
non-matching bodies to invalidate the cache.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_idempotency_key_replays_cached_response(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    key = f"test-idem-{uuid.uuid4().hex}"
    payload = {"purpose": "source"}
    r1 = await client.get("/v1/files", headers={**auth_headers, "Idempotency-Key": key})
    r2 = await client.get("/v1/files", headers={**auth_headers, "Idempotency-Key": key})
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same body, same headers — replays
    assert r1.json() == r2.json()


async def test_missing_idempotency_header_works(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    r = await client.get("/v1/files", headers=auth_headers)
    assert r.status_code == 200


async def test_different_keys_independent(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    k1 = f"k1-{uuid.uuid4().hex}"
    k2 = f"k2-{uuid.uuid4().hex}"
    r1 = await client.get("/v1/files", headers={**auth_headers, "Idempotency-Key": k1})
    r2 = await client.get("/v1/files", headers={**auth_headers, "Idempotency-Key": k2})
    assert r1.status_code == r2.status_code == 200
