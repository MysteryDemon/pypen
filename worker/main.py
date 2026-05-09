from __future__ import annotations

import argparse
import asyncio

from app.utils.logging_config import logger, setup_logging

from .config_loader import load_config, load_defaults
from .constants import CONFIG_FILE, LOG_FILE, READY_FLAG
from .project_manager import (
    cleanup_existing_projects,
    install_system_packages,
    start_all_projects,
)
from .s6_svc import async_s6_svc, rescan_services
from .signals import register_signal_handlers

async def _main_async(clusters: list[dict]) -> None:
    parser = argparse.ArgumentParser(description="Project Manager")
    parser.add_argument("--restart", action="store_true", help="Restart all projects")
    args = parser.parse_args()

    await cleanup_existing_projects()

    defaults = load_defaults(CONFIG_FILE)
    pacman_packages = defaults.get("pacman_packages") or []
    if pacman_packages:
        await asyncio.get_event_loop().run_in_executor(
            None, install_system_packages, pacman_packages
        )

    if args.restart:
        logger.info("Restarting project manager...")
        await asyncio.gather(
            *(
                async_s6_svc("-d", cluster["project_number"].replace(" ", "_"))
                for cluster in clusters
            )
        )
        await rescan_services()
    else:
        logger.info("Starting project manager...")
        await start_all_projects(clusters)

    try:
        READY_FLAG.parent.mkdir(parents=True, exist_ok=True)
        READY_FLAG.touch()
    except OSError as e:
        logger.warning(f"Could not write readiness flag {READY_FLAG}: {e}")

def run() -> None:
    setup_logging(log_file=LOG_FILE, level="DEBUG")

    clusters = load_config(CONFIG_FILE)
    register_signal_handlers(clusters)

    asyncio.run(_main_async(clusters))
