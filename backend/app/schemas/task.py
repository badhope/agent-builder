"""Task and batch Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Mirror the DB enums (string-valued for forward-compat)
TaskStateLiteral = Literal[
    "pending", "queued", "running", "succeeded", "failed", "cancelled", "expired",
]
TaskPriorityLiteral = Literal["low", "normal", "high"]


class TaskCreate(BaseModel):
    """Used by the JSON-only `POST /v1/convert` body form."""

    source_file_id: uuid.UUID
    target_format: str = Field(min_length=1, max_length=20)
    options: dict[str, Any] = Field(default_factory=dict)
    webhook_url: str | None = Field(default=None, max_length=2048)
    webhook_secret: str | None = Field(default=None, max_length=64)
    priority: TaskPriorityLiteral = "normal"
    idempotency_key: str | None = Field(default=None, max_length=120)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    batch_id: uuid.UUID | None
    batch_index: int | None
    source_file_id: uuid.UUID
    source_format: str
    source_filename: str
    target_format: str
    options_json: dict[str, Any]
    state: TaskStateLiteral
    priority: TaskPriorityLiteral
    backend: str | None
    output_file_id: uuid.UUID | None
    output_format: str | None
    output_size: int | None
    output_sha256: str | None
    error_code: str | None
    error_message: str | None
    error_details: dict[str, Any]
    progress_pct: int
    progress_message: str | None
    attempts: int
    max_attempts: int
    webhook_url: str | None
    webhook_delivered: bool
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None
    queue_time_ms: int | None
    processing_time_ms: int | None
    created_at: datetime
    updated_at: datetime


class TaskLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    level: int
    message: str
    source: str | None
    worker_id: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str | None
    description: str | None
    state: TaskStateLiteral
    total: int
    succeeded: int
    failed: int
    running: int
    archive_file_id: uuid.UUID | None
    archive_format: str
    webhook_url: str | None
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BatchReadWithItems(BatchRead):
    items: list[TaskRead] = Field(default_factory=list)


class BatchCreate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    items: list[TaskCreate] = Field(min_length=1, max_length=200)
    archive_format: str = Field(default="zip", pattern=r"^(zip|none)$")
    webhook_url: str | None = Field(default=None, max_length=2048)
    webhook_secret: str | None = Field(default=None, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=120)


class BatchLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    level: str
    event: str
    message: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class ProgressEvent(BaseModel):
    """WebSocket / pubsub progress event."""

    type: Literal["hello", "progress", "log", "completed", "failed", "cancelled", "expired"]
    task_id: uuid.UUID
    state: TaskStateLiteral | None = None
    progress_pct: int | None = None
    progress_message: str | None = None
    message: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    ts: int
