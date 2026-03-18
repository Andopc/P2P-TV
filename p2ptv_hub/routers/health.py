"""Health-check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import verify_token

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    dependencies=[Depends(verify_token)],
)
async def health() -> dict:
    return {"status": "ok"}
