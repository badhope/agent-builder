"""Webhook subscription schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class WebhookSubscriptionCreate(BaseModel):
    url: HttpUrl
    description: str | None = Field(default=None, max_length=200)
    events: list[str] = Field(default_factory=list)
    secret: str | None = Field(default=None, max_length=64)
    is_active: bool = True
    filter: dict[str, Any] = Field(default_factory=dict)


class WebhookSubscriptionUpdate(BaseModel):
    url: HttpUrl | None = None
    description: str | None = Field(default=None, max_length=200)
    events: list[str] | None = None
    secret: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None
    filter: dict[str, Any] | None = None


class WebhookSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    url: str
    description: str | None
    events: list[str]
    is_active: bool
    last_triggered_at: datetime | None
    last_status: int | None
    last_error: str | None
    total_delivered: int
    total_failed: int
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    url: str
    response_status: int | None
    duration_ms: int | None
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    delivered_at: datetime | None
    next_attempt_at: datetime | None
    created_at: datetime


class WebhookTestResult(BaseModel):
    status: str
    response_status: int | None
    duration_ms: int | None
    error: str | None
