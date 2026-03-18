"""Entry point for the P2P TV node helper.

Run directly:
    python -m p2ptv_node.main

Or via Docker:
    docker compose up node
"""

from __future__ import annotations

import logging
import time

from .config import get_settings
from .hub_client import HubClient
from .prefetcher import run_prefetch_cycle
from .qbt_client import QbtClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = get_settings()
    channel_ids = cfg.channel_ids()

    if not channel_ids:
        logger.warning(
            "P2PTV_CHANNEL_IDS is empty – node will not prefetch anything. "
            "Set it to a comma-separated list of channel IDs."
        )

    hub = HubClient(cfg.p2ptv_hub_url, cfg.p2ptv_api_key)
    logger.info(
        "Node helper starting – hub=%s  channels=%s  prefetch=%dh  cache=%s (%.1f GiB max)",
        cfg.p2ptv_hub_url,
        channel_ids or "(none)",
        cfg.p2ptv_prefetch_hours,
        cfg.p2ptv_cache_dir,
        cfg.p2ptv_cache_max_gb,
    )

    # Verify hub connectivity before entering the loop
    try:
        hub.health()
        logger.info("Hub reachable and API key valid.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot reach hub: %s – will keep retrying each cycle.", exc)

    while True:
        try:
            with QbtClient(cfg.qbt_url, cfg.qbt_username, cfg.qbt_password) as qbt:
                run_prefetch_cycle(
                    hub=hub,
                    qbt=qbt,
                    channel_ids=channel_ids,
                    prefetch_hours=cfg.p2ptv_prefetch_hours,
                    cache_dir=cfg.p2ptv_cache_dir,
                    cache_max_gb=cfg.p2ptv_cache_max_gb,
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("Prefetch cycle error: %s", exc)

        logger.info("Sleeping %d s until next cycle…", cfg.poll_interval_seconds)
        time.sleep(cfg.poll_interval_seconds)


if __name__ == "__main__":
    main()
