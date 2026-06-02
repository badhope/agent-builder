"""Format registry tests."""

from __future__ import annotations

from app.converters.registry import get_registry


def test_registry_loads():
    reg = get_registry()
    formats = reg.all_formats()
    assert "pdf" in formats
    assert "docx" in formats
    assert "md" in formats
    assert "png" in formats
    assert "json" in formats
    assert "csv" in formats


def test_adjacency_pdf():
    reg = get_registry()
    edges = reg.targets_for("pdf")
    target_fmts = {e.target for e in edges}
    assert "docx" in target_fmts
    assert "png" in target_fmts
    assert "txt" in target_fmts


def test_pick_converter_for_pdf_to_png():
    reg = get_registry()
    result = reg.lookup("pdf", "png")
    assert result is not None
    converter, edge = result
    assert edge.source == "pdf"
    assert edge.target == "png"
    assert converter is not None