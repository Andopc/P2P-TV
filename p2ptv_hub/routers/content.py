"""Content file-serving endpoint with HTTP Range support."""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import AsyncIterator

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..auth import verify_token
from ..store import FileStore

logger = logging.getLogger(__name__)
router = APIRouter(tags=["content"])

_CHUNK_SIZE = 1 << 16  # 64 KiB


def _store(request: Request) -> FileStore:
    return request.app.state.store


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    """Parse an HTTP ``Range: bytes=…`` header.

    Returns *(start, end)* as inclusive byte offsets.
    Raises ``ValueError`` on malformed input.
    """
    if not range_header.startswith("bytes="):
        raise ValueError("Only byte ranges are supported")
    spec = range_header[6:]

    if spec.startswith("-"):
        # Suffix range: last N bytes
        suffix = int(spec[1:])
        start = max(0, file_size - suffix)
        return start, file_size - 1

    parts = spec.split("-", 1)
    if len(parts) != 2:
        raise ValueError("Invalid range spec")
    start = int(parts[0])
    end = int(parts[1]) if parts[1] else file_size - 1
    return start, end


async def _file_range_stream(path: str, start: int, length: int) -> AsyncIterator[bytes]:
    async with aiofiles.open(path, "rb") as fh:
        await fh.seek(start)
        remaining = length
        while remaining > 0:
            chunk = await fh.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get(
    "/content/{content_id}/file",
    summary="Serve a content file with HTTP Range support",
    dependencies=[Depends(verify_token)],
    response_class=StreamingResponse,
)
async def serve_file(
    content_id: str,
    request: Request,
    store: FileStore = Depends(_store),
) -> StreamingResponse:
    file_path = store.get_content_path(content_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail=f"Content '{content_id}' not found")

    file_size = os.path.getsize(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    range_header = request.headers.get("range")
    if range_header:
        try:
            start, end = _parse_range(range_header, file_size)
        except ValueError as exc:
            raise HTTPException(
                status_code=416,
                detail=str(exc),
                headers={"Content-Range": f"bytes */{file_size}"},
            ) from exc

        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(
                status_code=416,
                detail="Range Not Satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        length = end - start + 1
        logger.debug("Range request %s: bytes %d-%d/%d", content_id, start, end, file_size)
        return StreamingResponse(
            _file_range_stream(file_path, start, length),
            status_code=206,
            media_type=mime_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            },
        )

    # Full file
    logger.debug("Full file request %s (%d bytes)", content_id, file_size)
    return StreamingResponse(
        _file_range_stream(file_path, 0, file_size),
        status_code=200,
        media_type=mime_type,
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        },
    )
