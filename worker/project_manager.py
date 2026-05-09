from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

from git import Repo

from app.utils.logging_config import logger

from .constants import APP_DIR, S6_SERVICE_DIR
from .pyenv_utils import get_pyenv_python, run_with_pyenv
from .s6_config import remove_service, write_service
from .s6_svc import (
    async_s6_svc,
    rescan_services,
    wait_for_process_stop,
)

def _project_dir(cluster: dict[str, Any]) -> Path:
    return APP_DIR / cluster["project_number"].replace(" ", "_")

def install_system_packages(packages: list[str]) -> None:
    if not packages:
        return

    pacman = shutil.which("pacman")
    if pacman is None:
        logger.warning(
            f"install_system_packages: pacman not found on PATH; skipping {packages}"
        )
        return

    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }

    cmd = [
        pacman, "-Sy", "--needed", "--noconfirm",
        *packages,
    ]
    logger.info(f"install_system_packages: running {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, env=env
        )
    except subprocess.TimeoutExpired:
        logger.error("install_system_packages: pacman install timed out after 600s")
        return
    except Exception as exc:
        logger.error(f"install_system_packages: pacman invocation failed: {exc}")
        return

    for line in (result.stdout or "").splitlines():
        logger.info(f"[pacman] {line}")
    for line in (result.stderr or "").splitlines():
        log_fn = logger.info if result.returncode == 0 else logger.error
        log_fn(f"[pacman] {line}")

    if result.returncode == 0:
        logger.info(f"install_system_packages: ok ({len(packages)} package(s))")
    else:
        logger.error(
            f"install_system_packages: pacman exited {result.returncode}; "
            f"projects depending on these packages may fail to start"
        )

def _prepare_project_dir(cluster: dict[str, Any]) -> None:
    project_dir = _project_dir(cluster)
    venv_dir = project_dir / "venv"
    requirements_file = project_dir / "requirements.txt"
    branch = cluster.get("branch", "main")

    if project_dir.exists():
        logger.info(f"Removing existing directory: {project_dir}")
        shutil.rmtree(project_dir)

    logger.info(
        f"Cloning {cluster['project_number']} from {cluster['git_url']} (branch: {branch})"
    )

    clone_target = cluster.get("clone_url") or cluster["git_url"]
    Repo.clone_from(clone_target, str(project_dir), branch=branch, single_branch=True)

    version = cluster.get("python_version")
    python_executable = (
        get_pyenv_python(version) if version else (shutil.which("python3") or "python3")
    )

    if not requirements_file.exists():
        return

    logger.info(
        f"Creating virtual environment for {cluster['project_number']} using {python_executable} (via uv)"
    )
    venv_cmd = ["uv", "venv", str(venv_dir), "--python", python_executable]
    pip_cmd = [
        "uv",
        "pip",
        "install",
        "--no-cache",
        "--python",
        str(venv_dir / "bin" / "python"),
        "-r",
        str(requirements_file),
    ]

    if version:
        run_with_pyenv(version, venv_cmd, check=True)
        run_with_pyenv(version, pip_cmd, check=True)
    else:
        subprocess.run(venv_cmd, check=True)
        subprocess.run(pip_cmd, check=True)

async def start_project(cluster: dict[str, Any]) -> None:
    logger.info(f"Starting project: {cluster['project_number']}")

    project_dir = _project_dir(cluster)
    venv_dir = project_dir / "venv"
    project_file = project_dir / cluster["run_command"]

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _prepare_project_dir, cluster)

    python_executable = venv_dir / "bin" / "python3"
    if cluster.get("python_version"):
        python_executable = venv_dir / "bin" / f"python{cluster['python_version']}"

    if project_file.suffix == ".sh":
        command = f"bash {project_file}"
    elif project_file.suffix == ".py":
        command = f"{python_executable} {project_file}"
    else:
        command = f"{python_executable} -m {project_file.stem}"

    write_service(cluster, command)

async def stop_project(project_number: str) -> None:
    logger.info(f"Stopping project: {project_number}")
    slug = project_number.replace(" ", "_")

    await async_s6_svc("-d", slug)
    if not await wait_for_process_stop(slug):
        logger.warning(f"Process {slug} did not stop within timeout.")

    remove_service(slug)

async def cleanup_existing_projects() -> None:
    if not S6_SERVICE_DIR.exists():
        S6_SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        return

    for service_dir in S6_SERVICE_DIR.iterdir():
        if not service_dir.is_dir():
            continue

        if service_dir.name.startswith("."):
            continue
        slug = service_dir.name
        await async_s6_svc("-d", slug)
        remove_service(slug)
        logger.info(f"Cleaned up s6 service: {slug}")
    await rescan_services()

async def start_all_projects(clusters: list[dict[str, Any]]) -> None:
    await asyncio.gather(*(start_project(cluster) for cluster in clusters))
    await rescan_services()

async def stop_all_projects(clusters: list[dict[str, Any]]) -> None:
    logger.info("Stopping all projects...")
    await asyncio.gather(*(stop_project(cluster["project_number"]) for cluster in clusters))
    await rescan_services()
