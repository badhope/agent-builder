"""File Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FileRead(BaseModel):
    """File metadata returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    filename: str
    content_type: str | None
    size: int
    purpose: str
    sha256: str | None
    format: str | None
    storage_backend: str
    storage_bucket: str | None
    storage_key: str
    scan_status: str
    scan_signature: str | None
    scan_at: datetime | None
    scan_engine: str | None
    metadata_json: dict = Field(default_factory=dict)
    thumbnail_id: uuid.UUID | None
    download_count: int
    last_downloaded_at: datetime | None
    expires_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FileUpdate(BaseModel):
    expires_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)


class FileSignedUrlResponse(BaseModel):
    url: str
    expires_in: int
    expires_at: datetime
