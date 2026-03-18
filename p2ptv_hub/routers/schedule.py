"""Channel schedule endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import verify_token
from ..models import ScheduleEntry
from ..store import FileStore

router = APIRouter(tags=["schedule"])


def _store(request: Request) -> FileStore:
    return request.app.state.store


@router.get(
    "/channels/{channel_id}/schedule",
    response_model=list[ScheduleEntry],
    summary="Return schedule entries for the next N hours",
    dependencies=[Depends(verify_token)],
)
async def get_schedule(
    channel_id: str,
    hours: int = Query(default=12, ge=1, le=168, description="Lookahead window in hours (1–168)."),
    store: FileStore = Depends(_store),
) -> list[ScheduleEntry]:
    if store.get_channel(channel_id) is None:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
    return store.get_schedule(channel_id, hours)
