from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from app.utils.logging_config import logger

from .naming import generate_prefix

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

_REQUIRED_KEYS = ("id", "git_url", "branch", "run_command")

_CRON_DEFAULTS: dict[str, Any] = {
    "restart_on": None,
    "redeploy": False,
    "idle": None,
    "pull_commits": True,
}

_DEFAULT_LOGS_SIZE_BYTES: int = 10 * 1024 * 1024

_SIZE_SUFFIXES: dict[str, int] = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024 * 1024,
    "MB": 1024 * 1024,
    "G": 1024 * 1024 * 1024,
    "GB": 1024 * 1024 * 1024,
}

def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)

def _coerce_optional_int(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _coerce_size_bytes(value: Any) -> int:
    if value in (None, "", 0, "0"):
        return _DEFAULT_LOGS_SIZE_BYTES
    if isinstance(value, (int, float)):
        return max(int(value), 4096)
    text = str(value).strip().upper().replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([A-Z]*)", text)
    if not match:
        return _DEFAULT_LOGS_SIZE_BYTES
    number, suffix = match.groups()
    multiplier = _SIZE_SUFFIXES.get(suffix)
    if multiplier is None:
        return _DEFAULT_LOGS_SIZE_BYTES
    return max(int(float(number) * multiplier), 4096)

def _normalize_pacman_packages(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        items = raw.split()
    elif isinstance(raw, (list, tuple)):
        items = [str(x) for x in raw]
    else:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out

def load_defaults(file_path: str) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        return {"pacman_packages": [], "ping": True, "ping_url": ""}
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        logger.error(f"load_defaults: TOML parse error in {file_path}: {exc}")
        return {"pacman_packages": [], "ping": True, "ping_url": ""}
    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        return {"pacman_packages": [], "ping": True, "ping_url": ""}
    ping_raw = defaults.get("ping", True)
    return {
        "pacman_packages": _normalize_pacman_packages(defaults.get("pacman_packages")),
        "ping": _coerce_bool(ping_raw) if ping_raw not in (None, "") else True,
        "ping_url": str(defaults.get("ping_url") or "").strip(),
    }

def _normalize_cron(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    return {
        "restart_on": _coerce_optional_int(raw.get("restart_on")),
        "redeploy": _coerce_bool(raw.get("redeploy", False)),
        "idle": _coerce_optional_int(raw.get("idle")),
        "pull_commits": _coerce_bool(raw.get("pull_commits", True)),
    }

def _normalize_repo_kind(raw: Any) -> str:
    if raw is None:
        return "public"
    text = str(raw).strip().lower()
    if text in ("private", "priv"):
        return "private"
    return "public"

_TOKEN_URL_RE = re.compile(r"^(https?://)(?:[^@/]+@)?(.+)$", re.IGNORECASE)

def inject_access_token(git_url: str, token: str | None) -> str:
    if not token:
        return git_url
    url = (git_url or "").strip()
    match = _TOKEN_URL_RE.match(url)
    if not match:
        return url
    scheme, rest = match.groups()

    return f"{scheme}x-access-token:{token}@{rest}"

def validate_config(projects: list[dict[str, Any]]) -> bool:
    seen_ids: set[str] = set()

    for project in projects:
        missing = [k for k in _REQUIRED_KEYS if not project.get(k)]
        if missing:
            logger.error(
                f"Missing required fields {missing} in project: {project.get('_raw_id', '<unnamed>')}"
            )
            return False

        if not str(project["git_url"]).startswith("http"):
            logger.error(f"Invalid git_url for project {project['_raw_id']}.")
            return False

        raw_id = project["_raw_id"]
        if raw_id in seen_ids:
            logger.error(f"Duplicate project id: {raw_id}")
            return False
        seen_ids.add(raw_id)

    logger.info("Configuration validation successful.")
    return True

def load_config(file_path: str) -> list[dict[str, Any]]:
    logger.info(f"Loading configuration from {file_path}")

    path = Path(file_path)
    if not path.exists():
        logger.error(f"Configuration file not found: {file_path}")
        return []

    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        logger.error(f"Error parsing TOML file: {e}")
        return []

    defaults = raw.get("defaults", {}) or {}
    default_python = defaults.get("python_version") or None
    default_token = (defaults.get("access_token") or "").strip() or None

    projects_raw = raw.get("project", []) or []
    if not isinstance(projects_raw, list):
        logger.error("[[project]] must be an array of tables.")
        return []

    projects: list[dict[str, Any]] = []
    for entry in projects_raw:
        raw_id = str(entry.get("id", "")).strip()
        if not raw_id:
            logger.warning("Skipping project with empty id.")
            continue

        prefix = generate_prefix().replace(" ", "_")
        namespaced_id = f"{prefix}_{raw_id}"

        project_python = entry.get("python_version") or None
        python_version = project_python or default_python

        repo_kind = _normalize_repo_kind(entry.get("repo"))
        project_token = (str(entry.get("access_token") or "")).strip() or None
        access_token = project_token or default_token if repo_kind == "private" else None
        if repo_kind == "private" and not access_token:
            logger.warning(
                f"Project {raw_id} is marked repo=\"private\" but no "
                f"access_token is set (project or [defaults]). Clones may fail."
            )

        git_url = str(entry.get("git_url", "")).strip()
        clone_url = inject_access_token(git_url, access_token)

        env = entry.get("env") or {}
        if not isinstance(env, dict):
            logger.warning(f"Ignoring non-table [project.env] for {raw_id}.")
            env = {}

        projects.append(
            {

                "id": namespaced_id,
                "project_number": namespaced_id,
                "name": namespaced_id,
                "_raw_id": raw_id,
                "git_url": git_url,

                "clone_url": clone_url,
                "repo": repo_kind,
                "access_token": access_token,
                "branch": str(entry.get("branch", "main")).strip() or "main",
                "run_command": str(entry.get("run_command", "")).strip(),
                "python_version": python_version,
                "env": {str(k): str(v) for k, v in env.items()},
                "cron": _normalize_cron(entry.get("cron")),
                "logs_size": _coerce_size_bytes(entry.get("logs_size")),
            }
        )

    if not validate_config(projects):
        raise ValueError("Invalid configuration file.")

    return projects
