"""Format / capability schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FormatInfo(BaseModel):
    name: str
    category: str
    description: str | None = None
    mime: str | None = None


class ConversionEdgeInfo(BaseModel):
    source: str
    target: str
    backends: list[str] = Field(default_factory=list)
    estimated_seconds: float | None = None


class FormatCatalog(BaseModel):
    formats: list[FormatInfo]
    edges: list[ConversionEdgeInfo]


class TargetFormats(BaseModel):
    source: str
    targets: list[str]
