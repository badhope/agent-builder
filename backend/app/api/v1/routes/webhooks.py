"""Webhook subscription + delivery routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Principal, require_user
from app.db.session import db_session
from app.schemas.common import Page
from app.schemas.webhook import (
    WebhookDeliveryRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
    WebhookSubscriptionUpdate,
    WebhookTestResult,
)
from app.services.webhook_service import WebhookService

router = APIRouter()


@router.get("/subscriptions", response_model=Page[WebhookSubscriptionRead])
async def list_subscriptions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        items, total = await WebhookService(session).list_subscriptions(
            principal.user_id, limit=limit, offset=offset,
        )
    return Page[WebhookSubscriptionRead](
        items=items, total=total, limit=limit, offset=offset,
    )


@router.post(
    "/subscriptions",
    response_model=WebhookSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    payload: WebhookSubscriptionCreate, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        sub = await WebhookService(session).create_subscription(
            principal.user_id,
            url=str(payload.url),
            events=payload.events,
            description=payload.description,
            secret=payload.secret,
            is_active=payload.is_active,
            filter=payload.filter,
        )
    return sub


@router.get(
    "/subscriptions/{subscription_id}",
    response_model=WebhookSubscriptionRead,
)
async def get_subscription(
    subscription_id: uuid.UUID, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        return await WebhookService(session).get_subscription(
            principal.user_id, subscription_id,
        )


@router.patch(
    "/subscriptions/{subscription_id}",
    response_model=WebhookSubscriptionRead,
)
async def update_subscription(
    subscription_id: uuid.UUID,
    payload: WebhookSubscriptionUpdate,
    principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        return await WebhookService(session).update_subscription(
            principal.user_id, subscription_id,
            url=str(payload.url) if payload.url else None,
            events=payload.events,
            description=payload.description,
            secret=payload.secret,
            is_active=payload.is_active,
            filter=payload.filter,
        )


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subscription(
    subscription_id: uuid.UUID, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        await WebhookService(session).delete_subscription(
            principal.user_id, subscription_id,
        )


@router.post(
    "/subscriptions/{subscription_id}/test",
    response_model=WebhookTestResult,
)
async def test_subscription(
    subscription_id: uuid.UUID, principal: Principal = Depends(require_user),
):
    async with db_session() as session:
        result = await WebhookService(session).test(
            principal.user, subscription_id,  # type: ignore[arg-type]
        )
    return WebhookTestResult(**result)


@router.get("/deliveries", response_model=list[WebhookDeliveryRead])
async def list_deliveries(
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_user),
):
    from sqlalchemy import desc, select

    from app.db.models.webhook import WebhookDelivery
    async with db_session() as session:
        stmt = (
            select(WebhookDelivery)
            .where(WebhookDelivery.user_id == principal.user_id)
            .order_by(desc(WebhookDelivery.created_at))
            .limit(limit)
        )
        rows = list((await session.execute(stmt)).scalars().all())
    return rows


__all__ = ["router"]
