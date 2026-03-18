"""Tests for GET /api/v1/health."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/health", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_no_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code in (401, 403)  # no Authorization header → unauthenticated


def test_health_bad_token(client: TestClient) -> None:
    resp = client.get("/api/v1/health", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401
