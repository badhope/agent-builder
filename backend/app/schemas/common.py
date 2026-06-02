"""Common Pydantic schemas: pagination, errors, IDs, etc."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    has_more: bool = False


class ErrorBody(BaseModel):
    """The canonical JSON error body returned by every API error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict | None = None
    request_id: str | None = None


class StatusRead(BaseModel):
    """Generic status response (used by long-running endpoints)."""

    status: str
    detail: str | None = None


__all__ = ["ErrorBody", "Page", "StatusRead"]
