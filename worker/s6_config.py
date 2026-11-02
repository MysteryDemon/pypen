from __future__ import annotations

import os
import stat
from typing import Any

from app.utils.logging_config import logger

from .constants import S6_LOG_DIR, S6_SERVICE_DIR

_RUN_TEMPLATE = """\
#!/bin/sh
exec 2>&1
cd {workdir}
{exports}exec {command}
"""

_LOG_RUN_TEMPLATE = """\
#!/bin/sh
mkdir -p {log_dir}
exec s6-log n1 s{size_bytes} {log_dir}
"""

_FINISH_TEMPLATE = """\
#!/bin/sh
exec sleep 1
"""

def _chmod_exec(path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def _format_exports(env: dict[str, str] | None) -> str:
    if not env:
        return ""
    lines = []
    for key, value in env.items():
        safe = str(value).replace("'", "'\\''")
        lines.append(f"export {key}='{safe}'")
    return "\n".join(lines) + "\n"

def write_service(cluster: dict[str, Any], command: str) -> None:
    slug = cluster["project_number"].replace(" ", "_")
    service_dir = S6_SERVICE_DIR / slug
    workdir = f"/app/{slug}"
    log_dir = S6_LOG_DIR / slug
    size_bytes = int(cluster.get("logs_size") or 10 * 1024 * 1024)

    logger.info(
        f"Writing s6 service for {cluster['project_number']} at {service_dir} "
        f"(log rotation @ {size_bytes} bytes)"
    )

    service_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    run_path = service_dir / "run"
    run_path.write_text(
        _RUN_TEMPLATE.format(
            slug=slug,
            workdir=workdir,
            exports=_format_exports(cluster.get("env")),
            command=command,
            size_bytes=size_bytes,
        )
    )
    _chmod_exec(run_path)

    finish_path = service_dir / "finish"
    finish_path.write_text(_FINISH_TEMPLATE)
    _chmod_exec(finish_path)

    log_service_dir = service_dir / "log"
    log_service_dir.mkdir(parents=True, exist_ok=True)
    log_run_path = log_service_dir / "run"
    log_run_path.write_text(
        _LOG_RUN_TEMPLATE.format(
            log_dir=str(log_dir),
            size_bytes=size_bytes,
        )
    )
    _chmod_exec(log_run_path)

    os.sync()
    logger.info(f"s6 service for {cluster['project_number']} written successfully.")

def remove_service(slug: str) -> None:
    service_dir = S6_SERVICE_DIR / slug
    if not service_dir.exists():
        return
    for child in service_dir.rglob("*"):
        try:
            if child.is_file() or child.is_symlink():
                child.unlink()
        except OSError:
            pass
    for child in sorted(
        service_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True
    ):
        try:
            if child.is_dir():
                child.rmdir()
        except OSError:
            pass
    try:
        service_dir.rmdir()
    except OSError:
        pass
    logger.info(f"Removed s6 service directory for {slug}.")
