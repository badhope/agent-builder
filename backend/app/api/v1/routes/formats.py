"""Format catalog routes: list formats, supported conversions, conversions for a file."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import Principal, get_current_principal
from app.converters.registry import get_registry

router = APIRouter()


@router.get("")
async def list_formats(principal: Principal = Depends(get_current_principal)):
    """List every format this server supports."""
    return {"formats": get_registry().all_formats()}


@router.get("/convertible")
async def convertible_formats(principal: Principal = Depends(get_current_principal)):
    """Adjacency list of supported conversions."""
    return {"edges": get_registry().adjacency_list()}


@router.get("/{fmt}/targets")
async def possible_targets(fmt: str, principal: Principal = Depends(get_current_principal)):
    return {"source": fmt.lower(), "targets": get_registry().targets_for(fmt)}


__all__ = ["router"]
