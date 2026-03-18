"""Shared pytest fixtures for the P2P TV test suite."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "test-secret-key"


@pytest.fixture(scope="session")
def data_dir() -> Generator[str, None, None]:
    """Temporary data directory populated with minimal fixture data."""
    tmp = tempfile.mkdtemp(prefix="p2ptv_test_data_")
    os.makedirs(os.path.join(tmp, "schedules"), exist_ok=True)
    content_dir = os.path.join(tmp, "content")
    os.makedirs(content_dir, exist_ok=True)

    # Channels
    channels = [
        {"id": "test-channel", "name": "Test Channel", "description": "Test", "variant": "handheld"},
        {"id": "crt-channel", "name": "CRT Channel", "description": "CRT", "variant": "crt"},
    ]
    with open(os.path.join(tmp, "channels.json"), "w") as fh:
        json.dump(channels, fh)

    # Schedule: two entries — one already airing, one upcoming
    now = datetime.now(timezone.utc)
    schedule = [
        {
            "start_ts": (now - timedelta(minutes=10)).isoformat(),
            "duration_seconds": 3600,
            "title": "Now Playing",
            "content_id": "test-clip",
            "variant": "handheld",
            "magnet": "magnet:?xt=urn:btih:" + "a" * 40,
            "sha256": "a" * 64,
            "size_bytes": 1024,
            "http_url": "",
        },
        {
            "start_ts": (now + timedelta(hours=2)).isoformat(),
            "duration_seconds": 1800,
            "title": "Coming Up",
            "content_id": "test-clip",
            "variant": "handheld",
            "magnet": "magnet:?xt=urn:btih:" + "b" * 40,
            "sha256": "b" * 64,
            "size_bytes": 512,
            "http_url": "",
        },
        {
            "start_ts": (now - timedelta(hours=3)).isoformat(),
            "duration_seconds": 1800,
            "title": "Already Aired",
            "content_id": "test-clip",
            "variant": "handheld",
            "magnet": "magnet:?xt=urn:btih:" + "c" * 40,
            "sha256": "c" * 64,
            "size_bytes": 512,
            "http_url": "",
        },
    ]
    with open(os.path.join(tmp, "schedules", "test-channel.json"), "w") as fh:
        json.dump(schedule, fh)

    # Tiny content file for file-serving tests
    content_path = os.path.join(content_dir, "test-clip.bin")
    content_bytes = b"Hello P2P TV! " * 100  # 1 400 bytes
    with open(content_path, "wb") as fh:
        fh.write(content_bytes)

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def client(data_dir: str) -> TestClient:
    """TestClient wired to the hub app with test credentials."""
    os.environ["P2PTV_API_KEY"] = TEST_API_KEY
    os.environ["P2PTV_DATA_DIR"] = data_dir
    os.environ["P2PTV_BASE_URL"] = "http://testserver"

    # Import app *after* setting env vars so get_settings() picks them up.
    from p2ptv_hub.config import get_settings
    get_settings.cache_clear()

    from p2ptv_hub.main import app
    from p2ptv_hub.store import FileStore
    app.state.store = FileStore(data_dir, "http://testserver")

    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_API_KEY}"}
