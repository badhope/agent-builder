"""Sanitizers tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import sanitizers


def test_sanitize_filename():
    assert sanitizers.sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitizers.sanitize_filename("normal.pdf") == "normal.pdf"
    assert sanitizers.sanitize_filename("a/b/c.txt") == "c.txt"
    assert sanitizers.sanitize_filename("..") == "untitled"
    assert sanitizers.sanitize_filename("") == "untitled"


def test_safe_join():
    root = "/tmp/safe"
    result = sanitizers.safe_join(root, "subdir", "a.pdf")
    expected = Path(root).resolve() / "subdir" / "a.pdf"
    assert Path(result) == expected


def test_safe_join_rejects_traversal():
    with pytest.raises(sanitizers.PathTraversalError):
        sanitizers.safe_join("/tmp/safe", "..", "..", "etc", "passwd")


def test_extension_of():
    assert sanitizers.extension_of("foo.PDF") == "pdf"
    assert sanitizers.extension_of("archive.tar.gz") == "gz"
    assert sanitizers.extension_of("noext") == ""