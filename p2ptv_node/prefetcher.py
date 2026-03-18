"""Core prefetch logic: poll schedule, add new magnets to qBittorrent."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .cache_manager import evict_if_needed
from .hub_client import HubClient
from .qbt_client import QbtClient

logger = logging.getLogger(__name__)


def _upcoming(entries: list[dict[str, Any]], horizon_hours: int) -> list[dict[str, Any]]:
    """Return entries whose start_ts falls within *horizon_hours* from now."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=horizon_hours)
    result = []
    for e in entries:
        start = datetime.fromisoformat(e["start_ts"])
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if now <= start <= cutoff:
            result.append(e)
    return result


def _end_ts_tag(entry: dict[str, Any]) -> str:
    """Build the ``end_ts=…`` tag string for the torrent."""
    start = datetime.fromisoformat(entry["start_ts"])
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(seconds=entry["duration_seconds"])
    return f"end_ts={end.isoformat()}"


def run_prefetch_cycle(
    hub: HubClient,
    qbt: QbtClient,
    channel_ids: list[str],
    prefetch_hours: int,
    cache_dir: str,
    cache_max_gb: float,
) -> None:
    """One full poll-and-prefetch cycle.

    1. Fetch schedule for each channel.
    2. Identify items within the prefetch horizon that are not yet in qBittorrent.
    3. Add missing magnets.
    4. Enforce the cache size limit.
    """
    # Build a set of magnets already known to qBittorrent
    try:
        existing_torrents = qbt.list_torrents()
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not list qBittorrent torrents: %s", exc)
        return

    existing_magnets: set[str] = set()
    for t in existing_torrents:
        # qBittorrent stores the magnet's infohash as the torrent hash
        h = t.get("hash", "").lower()
        if h:
            existing_magnets.add(h)

    new_count = 0
    for channel_id in channel_ids:
        try:
            entries = hub.get_schedule(channel_id, hours=prefetch_hours)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch schedule for %s: %s", channel_id, exc)
            continue

        upcoming = _upcoming(entries, prefetch_hours)
        logger.info(
            "Channel %s: %d total entries, %d within prefetch horizon",
            channel_id,
            len(entries),
            len(upcoming),
        )

        for entry in upcoming:
            magnet: str = entry.get("magnet", "")
            if not magnet:
                continue
            # Extract infohash from magnet URI to dedup
            ih = ""
            for part in magnet.split("&"):
                if part.startswith("xt=urn:btih:"):
                    ih = part.split(":")[-1].lower()
                    break
            if ih and ih in existing_magnets:
                logger.debug("Already seeding %s – skipping", entry.get("content_id"))
                continue

            tag = _end_ts_tag(entry)
            try:
                qbt.add_magnet(magnet, save_path=cache_dir)
                # qBittorrent doesn't let us set tags at add-time via simple API;
                # we'd need a second call.  Store the tag for eviction tracking.
                # (Full tag support can be added in a later iteration.)
                logger.info(
                    "Queued prefetch for %r (%s)",
                    entry.get("title"),
                    tag,
                )
                if ih:
                    existing_magnets.add(ih)
                new_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to add magnet for %s: %s",
                    entry.get("content_id"),
                    exc,
                )

    logger.info("Prefetch cycle complete – %d new torrent(s) added", new_count)

    # Evict old content if we're over the size limit
    try:
        evict_if_needed(qbt, cache_max_gb)
    except Exception as exc:  # noqa: BLE001
        logger.error("Cache eviction error: %s", exc)
