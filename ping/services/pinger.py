from __future__ import annotations

import time
from pathlib import Path

import requests

from app.utils.logging_config import logger

from ..config import MAX_FAILURES, REQUEST_TIMEOUT


def wait_for_ready_flag(flag_path: Path, poll_interval: int = 2) -> None:
    while not flag_path.exists():
        time.sleep(poll_interval)


def ping_once(session: requests.Session, url: str) -> bool:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        logger.error(f"Error pinging URL: {e}")
        return False

    if response.status_code == 200:
        logger.info(f"Ping successful: {response.status_code} - {url}")
        return True
    logger.warning(f"Ping failed with status: {response.status_code} - {url}")
    return False


def ping_loop(url: str, interval: int) -> None:
    failure_count = 0
    with requests.Session() as session:
        try:
            while True:
                if ping_once(session, url):
                    failure_count = 0
                else:
                    failure_count += 1
                    if failure_count >= MAX_FAILURES:
                        logger.error(
                            f"Maximum failure count reached ({MAX_FAILURES}). "
                            "Stopping ping function."
                        )
                        break
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Ping process interrupted by user.")
