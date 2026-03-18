"""Channels list endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import verify_token
from ..models import Channel
from ..store import FileStore

router = APIRouter(tags=["channels"])


def _store(request: Request) -> FileStore:
    return request.app.state.store


@router.get(
    "/channels",
    response_model=list[Channel],
    summary="List all channels",
    dependencies=[Depends(verify_token)],
)
async def list_channels(store: FileStore = Depends(_store)) -> list[Channel]:
    try:
        return store.get_channels()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="channels.json not found in data directory")
