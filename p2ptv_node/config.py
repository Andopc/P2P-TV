"""Node helper configuration (env vars or .env file)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NodeSettings(BaseSettings):
    """Configuration for the P2P TV node helper.

    All values can be set via environment variables or a ``.env`` file.
    """

    # Hub connection
    p2ptv_hub_url: str = "http://localhost:8000"
    p2ptv_api_key: str
    p2ptv_channel_ids: str = ""          # comma-separated, e.g. "channel-1,channel-crt"
    p2ptv_prefetch_hours: int = 6

    # Local cache
    p2ptv_cache_dir: str = "./cache"
    p2ptv_cache_max_gb: float = 10.0

    # qBittorrent WebAPI
    qbt_url: str = "http://localhost:8090"
    qbt_username: str = "admin"
    qbt_password: str = "adminadmin"

    # Polling interval (seconds)
    poll_interval_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("p2ptv_hub_url", "qbt_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    def channel_ids(self) -> list[str]:
        return [c.strip() for c in self.p2ptv_channel_ids.split(",") if c.strip()]


@lru_cache(maxsize=1)
def get_settings() -> NodeSettings:
    return NodeSettings()
