"""qBittorrent Web API client (session-cookie login)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class QbtClient:
    """Minimal qBittorrent WebAPI wrapper.

    Uses session-cookie authentication as required by qBittorrent's API v2.
    All requests re-use a single ``httpx.Client`` with the ``SID`` cookie.
    """

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url
        self._username = username
        self._password = password
        self._client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def login(self) -> None:
        """Authenticate and store the session cookie."""
        client = httpx.Client(timeout=15)
        resp = client.post(
            f"{self._base_url}/api/v2/auth/login",
            data={"username": self._username, "password": self._password},
        )
        resp.raise_for_status()
        if resp.text.strip().lower() != "ok.":
            raise RuntimeError(f"qBittorrent login failed: {resp.text!r}")
        self._client = client
        logger.info("Authenticated to qBittorrent at %s", self._base_url)

    def logout(self) -> None:
        if self._client:
            try:
                self._client.post(f"{self._base_url}/api/v2/auth/logout")
            except Exception:  # noqa: BLE001
                pass
            self._client.close()
            self._client = None

    def __enter__(self) -> "QbtClient":
        self.login()
        return self

    def __exit__(self, *_: Any) -> None:
        self.logout()

    # ------------------------------------------------------------------
    # Torrent management
    # ------------------------------------------------------------------

    @property
    def _c(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError("Not logged in – call login() first")
        return self._client

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def add_magnet(self, magnet: str, save_path: str) -> None:
        """Add a magnet link to qBittorrent, saving to *save_path*."""
        resp = self._c.post(
            f"{self._base_url}/api/v2/torrents/add",
            data={"urls": magnet, "savepath": save_path},
        )
        resp.raise_for_status()
        logger.info("Added magnet to qBittorrent: %s…", magnet[:60])

    def list_torrents(self) -> list[dict[str, Any]]:
        """Return the list of torrents from qBittorrent."""
        resp = self._c.get(f"{self._base_url}/api/v2/torrents/info")
        resp.raise_for_status()
        return resp.json()  # type: ignore[return-value]

    def delete_torrent(self, torrent_hash: str, delete_files: bool = True) -> None:
        """Remove a torrent (and optionally its files) from qBittorrent."""
        resp = self._c.post(
            f"{self._base_url}/api/v2/torrents/delete",
            data={"hashes": torrent_hash, "deleteFiles": str(delete_files).lower()},
        )
        resp.raise_for_status()
        logger.info("Deleted torrent %s (delete_files=%s)", torrent_hash, delete_files)
