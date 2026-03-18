"""Hub configuration loaded from environment variables."""

from __future__ import annotations

import sys
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class HubSettings(BaseSettings):
    """All configuration for the P2P TV hub.

    Required env vars:
        P2PTV_API_KEY  – shared secret used for Bearer auth on all API endpoints.

    Optional env vars:
        P2PTV_BASE_URL – externally reachable URL of this hub instance
                         (used to build ``http_url`` in schedule responses).
        P2PTV_DATA_DIR – path to the data directory (default: ``./data``).
    """

    p2ptv_api_key: str
    p2ptv_base_url: str = "http://localhost:8000"
    p2ptv_data_dir: str = "./data"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("p2ptv_api_key")
    @classmethod
    def api_key_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("P2PTV_API_KEY must not be empty")
        return v

    @field_validator("p2ptv_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> HubSettings:
    """Return (cached) hub settings.  Exits with a clear error if config is invalid."""
    try:
        return HubSettings()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: invalid hub configuration – {exc}", file=sys.stderr)
        sys.exit(1)
