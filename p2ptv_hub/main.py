"""FastAPI application entry point for the P2P TV hub."""

from __future__ import annotations

import logging

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .config import get_settings
from .store import FileStore
from .routers import channels, content, health, schedule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Validate config (exits on bad config) and wire up the store.
    cfg = get_settings()
    app.state.store = FileStore(cfg.p2ptv_data_dir, cfg.p2ptv_base_url)
    logger.info(
        "P2P TV Hub starting – base_url=%s  data_dir=%s",
        cfg.p2ptv_base_url,
        cfg.p2ptv_data_dir,
    )
    yield
    logger.info("P2P TV Hub stopped.")


app = FastAPI(
    title="P2P TV Hub",
    version="0.1.0",
    description=(
        "Home-hosted channel schedule hub and AV1 content server "
        "for the P2P TV project."
    ),
    lifespan=_lifespan,
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(schedule.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
