"""HTTP client for the P2P TV hub API."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class HubClient:
    """Thin wrapper around the hub's REST API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._headers = {"Authorization": f"Bearer {api_key}"}

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def get_schedule(self, channel_id: str, hours: int = 6) -> list[dict[str, Any]]:
        """Fetch schedule entries for *channel_id* covering the next *hours* hours."""
        url = f"{self._base_url}/api/v1/channels/{channel_id}/schedule"
        with httpx.Client(headers=self._headers, timeout=15) as client:
            resp = client.get(url, params={"hours": hours})
            resp.raise_for_status()
            data: list[dict[str, Any]] = resp.json()
            logger.info(
                "Fetched %d schedule entries for channel %s (horizon=%dh)",
                len(data),
                channel_id,
                hours,
            )
            return data

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def health(self) -> bool:
        """Return True if the hub is reachable and auth works."""
        url = f"{self._base_url}/api/v1/health"
        with httpx.Client(headers=self._headers, timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json().get("status") == "ok"
