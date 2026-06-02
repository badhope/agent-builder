"""Format catalog API tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_list_formats(client: AsyncClient) -> None:
    r = await client.get("/v1/formats")
    assert r.status_code == 200
    body = r.json()
    assert "formats" in body
    fmts = body["formats"]
    assert "pdf" in fmts


async def test_convertible_pairs(client: AsyncClient) -> None:
    r = await client.get("/v1/formats/convertible")
    assert r.status_code == 200
    body = r.json()
    assert "edges" in body
    edges = body["edges"]
    assert isinstance(edges, list)
    for edge in edges:
        assert "source" in edge
        assert "target" in edge


async def test_pdf_targets(client: AsyncClient) -> None:
    r = await client.get("/v1/formats/pdf/targets")
    assert r.status_code == 200
    body = r.json()
    assert "source" in body
    assert body["source"] == "pdf"
    assert "targets" in body
    target_fmts = {t.get("target") if isinstance(t, dict) else t.target for t in body["targets"]}
    assert any("text" in t or "docx" in t for t in target_fmts)