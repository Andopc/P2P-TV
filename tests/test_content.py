"""Tests for GET /api/v1/content/{content_id}/file (with Range support)."""

from __future__ import annotations

from fastapi.testclient import TestClient

_CONTENT_BYTES = b"Hello P2P TV! " * 100  # 1 400 bytes – matches conftest fixture
_CONTENT_ID = "test-clip"


def test_full_file(client: TestClient, auth_headers: dict) -> None:
    resp = client.get(f"/api/v1/content/{_CONTENT_ID}/file", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content == _CONTENT_BYTES
    assert resp.headers["accept-ranges"] == "bytes"


def test_range_request_middle(client: TestClient, auth_headers: dict) -> None:
    headers = {**auth_headers, "Range": "bytes=0-99"}
    resp = client.get(f"/api/v1/content/{_CONTENT_ID}/file", headers=headers)
    assert resp.status_code == 206
    assert resp.content == _CONTENT_BYTES[0:100]
    assert resp.headers["content-range"] == f"bytes 0-99/{len(_CONTENT_BYTES)}"
    assert resp.headers["content-length"] == "100"


def test_range_request_open_end(client: TestClient, auth_headers: dict) -> None:
    start = 100
    headers = {**auth_headers, "Range": f"bytes={start}-"}
    resp = client.get(f"/api/v1/content/{_CONTENT_ID}/file", headers=headers)
    assert resp.status_code == 206
    assert resp.content == _CONTENT_BYTES[start:]
    expected_len = len(_CONTENT_BYTES) - start
    assert resp.headers["content-length"] == str(expected_len)


def test_range_request_suffix(client: TestClient, auth_headers: dict) -> None:
    headers = {**auth_headers, "Range": "bytes=-200"}
    resp = client.get(f"/api/v1/content/{_CONTENT_ID}/file", headers=headers)
    assert resp.status_code == 206
    assert resp.content == _CONTENT_BYTES[-200:]


def test_range_out_of_bounds(client: TestClient, auth_headers: dict) -> None:
    headers = {**auth_headers, "Range": f"bytes=99999-99999"}
    resp = client.get(f"/api/v1/content/{_CONTENT_ID}/file", headers=headers)
    assert resp.status_code == 416


def test_content_not_found(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/content/nonexistent-file/file", headers=auth_headers)
    assert resp.status_code == 404


def test_content_requires_auth(client: TestClient) -> None:
    resp = client.get(f"/api/v1/content/{_CONTENT_ID}/file")
    assert resp.status_code in (401, 403)
