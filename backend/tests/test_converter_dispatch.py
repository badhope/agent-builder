"""End-to-end-ish conversion dispatcher tests.

These use the local storage backend and the in-process worker to convert
small text fixtures between formats. They are slow (real LibreOffice / Pandoc
binaries must be available); they are skipped when the binary is missing.
"""

from __future__ import annotations

import shutil

import pytest


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


pytestmark = pytest.mark.skipif(
    not have("pandoc"),
    reason="pandoc binary not available",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_text_to_html_via_dispatcher(client, auth_headers, tmp_path):
    body = b"# Hello\n\nThis is **markdown**."
    r = await client.post(
        "/v1/files/uploads",
        params={"purpose": "source"},
        files={"file": ("hello.md", body, "text/markdown")},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    file_id = r.json()["id"]

    r = await client.post(
        "/v1/convert",
        params={"source_file_id": file_id, "target_format": "html"},
        headers=auth_headers,
    )
    assert r.status_code == 202, r.text
    task = r.json()
    assert task["target_format"] == "html"
