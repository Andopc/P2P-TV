"""Cache eviction logic: enforces max-disk-size limit."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .qbt_client import QbtClient

logger = logging.getLogger(__name__)

_GB = 1 << 30  # bytes per GiB


def _torrent_end_ts(torrent: dict[str, Any]) -> datetime:
    """Estimate end-of-air time from qBittorrent torrent metadata.

    We store the ``end_ts`` tag on each torrent when we add it.
    Falls back to the completion timestamp if the tag is absent.
    """
    tag: str | None = None
    for t in (torrent.get("tags") or "").split(","):
        if t.strip().startswith("end_ts="):
            tag = t.strip()[len("end_ts="):]
            break
    if tag:
        try:
            dt = datetime.fromisoformat(tag)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    # Fall back: use completion time (seconds since epoch)
    completed = torrent.get("completion_on", 0) or 0
    return datetime.fromtimestamp(completed, tz=timezone.utc)


def evict_if_needed(qbt: QbtClient, max_gb: float) -> None:
    """Delete the oldest (by end_ts) already-aired torrents until under *max_gb*.

    Only removes torrents that have already aired (``end_ts`` is in the past).
    """
    torrents = qbt.list_torrents()
    if not torrents:
        return

    total_bytes: int = sum(t.get("size", 0) for t in torrents)
    max_bytes = int(max_gb * _GB)

    if total_bytes <= max_bytes:
        logger.debug(
            "Cache OK: %.2f GiB used / %.2f GiB max",
            total_bytes / _GB,
            max_gb,
        )
        return

    logger.warning(
        "Cache %.2f GiB exceeds limit %.2f GiB – starting eviction",
        total_bytes / _GB,
        max_gb,
    )

    now = datetime.now(timezone.utc)
    # Only consider torrents whose airtime has passed
    evictable = [t for t in torrents if _torrent_end_ts(t) < now]
    # Sort oldest end_ts first
    evictable.sort(key=_torrent_end_ts)

    for torrent in evictable:
        if total_bytes <= max_bytes:
            break
        size = torrent.get("size", 0)
        h = torrent.get("hash", "")
        name = torrent.get("name", h)
        logger.info("Evicting torrent %r (%s, %.2f MiB)", name, h, size / (1 << 20))
        try:
            qbt.delete_torrent(h, delete_files=True)
            total_bytes -= size
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to delete torrent %s: %s", h, exc)
