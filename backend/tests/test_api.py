"""Basic API smoke tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_openapi_includes_v1(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/v1/auth/login" in paths
    assert "/v1/convert" in paths
    assert "/v1/tasks" in paths
    assert "/v1/files/uploads" in paths


@pytest.mark.asyncio
@pytest.mark.integration
async def test_login_round_trip(client, test_user):
    r = await client.post(
        "/v1/auth/login",
        json={"email": test_user.email, "password": "Sup3rStrong!Pass"},
    )
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client):
    r = await client.get("/v1/tasks")
    assert r.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_me_returns_user(client, auth_headers, test_user):
    r = await client.get("/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == test_user.email
