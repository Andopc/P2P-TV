"""Tests for GET /api/v1/channels/{channel_id}/schedule."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_schedule_returns_entries(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/channels/test-channel/schedule", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # "Now Playing" and "Coming Up" should both be in a 12-hour window
    assert len(data) >= 2


def test_schedule_excludes_past_entries(client: TestClient, auth_headers: dict) -> None:
    resp = client.get(
        "/api/v1/channels/test-channel/schedule",
        params={"hours": 12},
        headers=auth_headers,
    )
    titles = {e["title"] for e in resp.json()}
    assert "Already Aired" not in titles


def test_schedule_entry_fields(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/channels/test-channel/schedule", headers=auth_headers)
    entry = resp.json()[0]
    for field in ("start_ts", "duration_seconds", "title", "content_id",
                  "variant", "magnet", "sha256", "size_bytes", "http_url"):
        assert field in entry, f"Missing field: {field}"


def test_schedule_http_url_contains_content_endpoint(
    client: TestClient, auth_headers: dict
) -> None:
    resp = client.get("/api/v1/channels/test-channel/schedule", headers=auth_headers)
    entry = resp.json()[0]
    assert "/api/v1/content/" in entry["http_url"]
    assert entry["content_id"] in entry["http_url"]


def test_schedule_unknown_channel(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/channels/nonexistent/schedule", headers=auth_headers)
    assert resp.status_code == 404


def test_schedule_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/channels/test-channel/schedule")
    assert resp.status_code in (401, 403)


def test_schedule_hours_param_validation(client: TestClient, auth_headers: dict) -> None:
    # hours=0 is below minimum
    resp = client.get(
        "/api/v1/channels/test-channel/schedule",
        params={"hours": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422
