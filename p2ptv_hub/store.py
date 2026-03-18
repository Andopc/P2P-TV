"""File-backed data store for channels, schedules and content files."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import Channel, ScheduleEntry

logger = logging.getLogger(__name__)


class FileStore:
    """Reads hub data from the local ``data/`` directory tree."""

    def __init__(self, data_dir: str, base_url: str) -> None:
        self.data_dir = data_dir
        self.base_url = base_url

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def get_channels(self) -> list[Channel]:
        path = os.path.join(self.data_dir, "channels.json")
        with open(path) as fh:
            raw = json.load(fh)
        return [Channel(**ch) for ch in raw]

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        for ch in self.get_channels():
            if ch.id == channel_id:
                return ch
        return None

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    def get_schedule(self, channel_id: str, hours: int = 12) -> list[ScheduleEntry]:
        """Return schedule entries whose window overlaps [now, now + hours]."""
        path = os.path.join(self.data_dir, "schedules", f"{channel_id}.json")
        if not os.path.exists(path):
            logger.warning("No schedule file for channel %s at %s", channel_id, path)
            return []

        with open(path) as fh:
            raw: list[dict] = json.load(fh)

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)
        entries: list[ScheduleEntry] = []

        for item in raw:
            start_ts = datetime.fromisoformat(item["start_ts"])
            if start_ts.tzinfo is None:
                start_ts = start_ts.replace(tzinfo=timezone.utc)
            end_ts = start_ts + timedelta(seconds=item["duration_seconds"])

            # Include items that overlap with the query window
            if end_ts >= now and start_ts <= cutoff:
                item = dict(item)  # shallow copy to avoid mutating cached data
                item["start_ts"] = start_ts.isoformat()
                item["http_url"] = (
                    f"{self.base_url}/api/v1/content/{item['content_id']}/file"
                )
                entries.append(ScheduleEntry(**item))

        return entries

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def get_content_path(self, content_id: str) -> Optional[str]:
        """Resolve *content_id* to an absolute file path, or return None."""
        content_dir = os.path.join(self.data_dir, "content")
        if not os.path.isdir(content_dir):
            return None
        for fname in os.listdir(content_dir):
            stem = os.path.splitext(fname)[0]
            if fname == content_id or stem == content_id:
                full = os.path.join(content_dir, fname)
                if os.path.isfile(full):
                    return full
        return None
