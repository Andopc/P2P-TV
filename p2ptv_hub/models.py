"""Pydantic data models shared across the hub."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Channel(BaseModel):
    """A broadcast channel definition."""

    id: str
    name: str
    description: str = ""
    variant: str = Field(
        default="handheld",
        description="Display profile: 'handheld' (Steam Deck) or 'crt' (Pi/4:3 display).",
    )


class ScheduleEntry(BaseModel):
    """A single programme entry in a channel schedule."""

    start_ts: datetime = Field(description="Programme start time (ISO 8601 / UTC).")
    duration_seconds: int = Field(gt=0)
    title: str
    content_id: str
    variant: str = Field(description="'handheld' or 'crt'.")
    magnet: str = Field(description="BitTorrent magnet URI for this content.")
    sha256: str = Field(description="SHA-256 hex digest of the content file.")
    size_bytes: int = Field(gt=0, description="File size in bytes.")
    http_url: str = Field(description="Hub URL to fetch the file directly.")
