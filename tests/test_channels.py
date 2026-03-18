"""Tests for GET /api/v1/channels."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_channels(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/channels", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    ids = {ch["id"] for ch in data}
    assert "test-channel" in ids
    assert "crt-channel" in ids


def test_channel_fields(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/channels", headers=auth_headers)
    ch = resp.json()[0]
    assert "id" in ch
    assert "name" in ch
    assert "variant" in ch


def test_channels_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/channels")
    assert resp.status_code in (401, 403)
