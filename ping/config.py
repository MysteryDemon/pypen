from __future__ import annotations

import os
import sys

from app.utils.logging_config import logger

DEFAULT_PING_INTERVAL = 240
DEFAULT_DELAY = 300
MAX_FAILURES = 5
REQUEST_TIMEOUT = 10
LOG_FILE = "ping_server.log"


def normalize_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return value
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


_normalize_url = normalize_url


def _detect_platform_url() -> str | None:
    for var in (
        "APP_URL",
        "RENDER_EXTERNAL_URL",
        "RAILWAY_STATIC_URL",
        "KOYEB_PUBLIC_URL",
        "DETA_SPACE_APP_HOSTNAME",
    ):
        val = os.getenv(var)
        if val:
            return _normalize_url(val)

    for var in (
        "RAILWAY_PUBLIC_DOMAIN",
        "KOYEB_PUBLIC_DOMAIN",
        "RENDER_EXTERNAL_HOSTNAME",
        "VERCEL_URL",
    ):
        val = os.getenv(var)
        if val:
            return _normalize_url(val)

    fly_app = os.getenv("FLY_APP_NAME")
    if fly_app:
        return f"https://{fly_app}.fly.dev"
    heroku_app = os.getenv("HEROKU_APP_NAME")
    if heroku_app:
        return f"https://{heroku_app}.herokuapp.com"

    return None


def get_app_url() -> str | None:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return _normalize_url(sys.argv[1])

    detected = _detect_platform_url()
    if detected:
        return detected

    return None


def get_ping_interval() -> int:
    try:
        return int(os.getenv("PING_INTERVAL", DEFAULT_PING_INTERVAL))
    except ValueError:
        logger.warning("Invalid PING_INTERVAL value; using default.")
        return DEFAULT_PING_INTERVAL


def get_startup_delay() -> int:
    try:
        return int(os.getenv("DELAY", DEFAULT_DELAY))
    except ValueError:
        logger.warning(f"Invalid DELAY value; using default {DEFAULT_DELAY} seconds.")
        return DEFAULT_DELAY


def should_delay_ping() -> bool:
    return os.getenv("DELAY_PING", "False").lower() in ("true", "1", "yes")
