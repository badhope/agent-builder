"""Batch schemas.

Re-exported from :mod:`app.schemas.task` for namespace convenience, plus
batch-specific lightweight helper models used in the batch API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import (
    BatchCreate,
    BatchLogRead,
    BatchRead,
    BatchReadWithItems,
    TaskStateLiteral,
)


class BatchSummary(BaseModel):
    """A compact, list-friendly batch projection used in dashboards."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str | None
    state: TaskStateLiteral
    total: int
    succeeded: int
    failed: int
    running: int
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


class BatchProgress(BaseModel):
    """Live progress snapshot for a batch."""

    batch_id: uuid.UUID
    state: TaskStateLiteral
    total: int
    succeeded: int
    failed: int
    running: int
    queued: int
    progress_pct: float = Field(ge=0.0, le=100.0)


class BatchArchiveInfo(BaseModel):
    """Metadata for the optional archive file produced when a batch finishes."""

    archive_file_id: uuid.UUID | None
    archive_format: str
    size_bytes: int | None
    sha256: str | None
    download_url: str | None
    expires_at: datetime | None


class BatchActionResponse(BaseModel):
    """Returned by batch retry / cancel endpoints."""

    batch_id: uuid.UUID
    affected_tasks: int
    state: TaskStateLiteral
    message: str


class BatchListResponse(BaseModel):
    items: list[BatchRead]
    total: int
    limit: int
    offset: int


class BatchRetryRequest(BaseModel):
    """Request body for ``POST /v1/batches/{id}/retry``."""

    only_failed: bool = True
    reset_state: bool = True


class BatchCancelRequest(BaseModel):
    """Request body for ``POST /v1/batches/{id}/cancel``."""

    reason: str | None = Field(default=None, max_length=500)


class BatchLogFilter(BaseModel):
    """Filter used by ``GET /v1/batches/{id}/logs``."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None
    event: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class BatchLogListResponse(BaseModel):
    items: list[BatchLogRead]
    total: int
    has_more: bool


class BatchCreateResponse(BaseModel):
    batch: BatchRead
    items: list[uuid.UUID] = Field(
        description="Task IDs created for this batch, in submission order.",
    )


class BatchStatsResponse(BaseModel):
    """Per-state counts and timing aggregates for a batch."""

    batch_id: uuid.UUID
    state: TaskStateLiteral
    counts: dict[str, int]
    avg_processing_ms: float | None
    p95_processing_ms: float | None
    total_size_in: int
    total_size_out: int
    formats_in: dict[str, int]
    formats_out: dict[str, int]
    by_backend: dict[str, int]
    by_error_code: dict[str, int]
    updated_at: datetime


__all__ = [
    "BatchActionResponse",
    "BatchArchiveInfo",
    "BatchCancelRequest",
    "BatchCreate",
    "BatchCreateResponse",
    "BatchListResponse",
    "BatchLogFilter",
    "BatchLogListResponse",
    "BatchLogRead",
    "BatchProgress",
    "BatchRead",
    "BatchReadWithItems",
    "BatchRetryRequest",
    "BatchStatsResponse",
    "BatchSummary",
]
