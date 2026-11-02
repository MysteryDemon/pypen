import os
import shutil
import subprocess
import re
import sys
import asyncio
from datetime import datetime
from functools import wraps
from pathlib import Path
from collections import defaultdict, deque

try:
    import psutil
except Exception:
    psutil = None

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from app import app, sio
from app.utils.logging_config import logger
from itsdangerous import BadSignature
from quart import (
    request, jsonify, redirect, url_for, session, Response,
    send_from_directory,
)
from socketio.exceptions import ConnectionRefusedError as SocketRefused
from werkzeug.exceptions import HTTPException

DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "web" / "out"

S6_LOG_DIR = "/var/log/s6"
S6_SERVICE_DIR = "/etc/s6/services"
CONFIG_FILE = Path("/app/project.toml")
STATUS_CHECK_INTERVAL = 2
MAX_STATUS_CHECK_ATTEMPTS = 10

STOPPED_SERVICE_SCRIPTS: dict[str, str] = {}

FAILURE_COUNTS = defaultdict(int)
MAX_FAILURES_BEFORE_PAUSE = 5
PAUSED_BY_SYSTEM = set()

_VALID_NAME_RE = re.compile(r'^[a-zA-Z0-9_\- ]+$')

CPU_HISTORY_LEN = 30
_CPU_HISTORY: dict[str, deque[float]] = defaultdict(
    lambda: deque(maxlen=CPU_HISTORY_LEN)
)

_CPU_PROC_CACHE: dict = {}

_CPU_CORE_COUNT = max(1, (os.cpu_count() or 1))

def _sample_cpu(process_name: str, pid: str | int | None) -> float | None:
    if psutil is None or pid in (None, "", "-"):
        return None
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return None
    proc = _CPU_PROC_CACHE.get(pid_int)
    try:
        if proc is None or not proc.is_running() or proc.pid != pid_int:
            proc = psutil.Process(pid_int)
            _CPU_PROC_CACHE[pid_int] = proc

            proc.cpu_percent(interval=None)
            cpu = 0.0
        else:
            cpu = float(proc.cpu_percent(interval=None))
    except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
        _CPU_PROC_CACHE.pop(pid_int, None)
        return None
    except Exception:
        return None

    cpu_norm = max(0.0, min(100.0, cpu / _CPU_CORE_COUNT))
    _CPU_HISTORY[process_name].append(cpu_norm)
    return cpu_norm

def _cpu_history_for(process_name: str) -> list[float]:
    history = _CPU_HISTORY.get(process_name)
    return [round(v, 2) for v in history] if history else []

def _slug(process_name: str) -> str:
    return process_name.replace(" ", "_")

def _svc_path(process_name: str) -> Path:
    return Path(S6_SERVICE_DIR) / _slug(process_name)

def _run_cmd(cmd: list[str], timeout: int = 30, quiet: bool = False) -> dict:
    log = logger.debug if quiet else logger.info
    err_log = logger.debug if quiet else logger.error
    try:
        log(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.stdout:
            log(f"Command output: {result.stdout.strip()}")
        if result.stderr and result.returncode != 0:
            err_log(f"Command error: {result.stderr.strip()}")
        if result.returncode == 0:
            return {"status": "success", "message": result.stdout.strip()}
        return {"status": "error", "message": (result.stderr or result.stdout).strip()}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def s6_svstat(process_name: str) -> dict | None:
    svc = _svc_path(process_name)
    if not svc.is_dir():
        return None
    res = _run_cmd(["s6-svstat", str(svc)], timeout=5, quiet=True)
    if res["status"] != "success":
        return None
    line = res["message"]
    pid_match = re.search(r'pid (\d+)', line)
    pid = pid_match.group(1) if pid_match else None
    uptime_match = re.search(r'(\d+) seconds', line)
    uptime_seconds = int(uptime_match.group(1)) if uptime_match else 0

    if line.startswith("up "):
        status = "RUNNING"
    elif line.startswith("down "):
        status = "BACKOFF" if "want up" in line else "STOPPED"
    else:
        status = "UNKNOWN"

    paused = bool(pid) and is_process_paused(pid)

    hours, rem = divmod(uptime_seconds, 3600)
    minutes, secs = divmod(rem, 60)
    uptime = f"{hours}:{minutes:02d}:{secs:02d}"

    cpu_pct: float | None = None
    if status == "RUNNING" and pid and not paused:
        cpu_pct = _sample_cpu(process_name, pid)
    cpu_history = _cpu_history_for(process_name)

    return {
        "name": process_name,
        "status": status,
        "pid": pid,
        "uptime": uptime,
        "paused": paused,
        "cpu": round(cpu_pct, 2) if cpu_pct is not None else None,
        "cpu_history": cpu_history,
    }

def list_services() -> list[str]:
    try:
        return sorted(
            p.name for p in Path(S6_SERVICE_DIR).iterdir()
            if p.is_dir() and not p.name.startswith('.')
        )
    except FileNotFoundError:
        return []

def _configured_project_ids() -> list[str]:
    try:
        with CONFIG_FILE.open("rb") as fh:
            raw = tomllib.load(fh)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return []
    projects = raw.get("project") or []
    if not isinstance(projects, list):
        return []
    out: list[str] = []
    for entry in projects:
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get("id", "")).strip()
        if pid:
            out.append(pid)
    return out

def _placeholder_for(raw_id: str) -> dict:
    return {
        "name": raw_id,
        "status": "PENDING",
        "pid": None,
        "uptime": "0:00:00",
        "paused": False,
        "auto_paused": False,
        "cpu": None,
        "cpu_history": [],
    }

def _collect_processes() -> list[dict]:
    services = list_services()
    processes: list[dict] = []
    needs_rescan = False
    for name in services:
        parsed = s6_svstat(name)
        if not parsed:

            needs_rescan = True
            processes.append({
                "name": name,
                "status": "PENDING",
                "pid": None,
                "uptime": "0:00:00",
                "paused": False,
                "auto_paused": False,
                "cpu": None,
                "cpu_history": [],
            })
            continue
        pname = parsed["name"]
        if parsed["status"] == "BACKOFF":
            FAILURE_COUNTS[pname] += 1
            if FAILURE_COUNTS[pname] >= MAX_FAILURES_BEFORE_PAUSE and pname not in PAUSED_BY_SYSTEM:
                logger.warning(
                    f"Process {pname} has failed {FAILURE_COUNTS[pname]} times, auto-pausing"
                )
                PAUSED_BY_SYSTEM.add(pname)
                s6_svc("-d", pname)
            parsed["auto_paused"] = pname in PAUSED_BY_SYSTEM
        else:
            if parsed["status"] == "RUNNING":
                FAILURE_COUNTS[pname] = 0
                PAUSED_BY_SYSTEM.discard(pname)
            parsed["auto_paused"] = pname in PAUSED_BY_SYSTEM
        processes.append(parsed)

    if needs_rescan:
        s6_rescan()

    configured = _configured_project_ids()
    order: dict[str, int] = {}
    for position, raw_id in enumerate(configured):
        order.setdefault(raw_id.replace(" ", "_"), position)

    started = {_config_position(svc, order) for svc in services}
    for raw_id in configured:
        if order[raw_id.replace(" ", "_")] not in started:
            processes.append(_placeholder_for(raw_id))

    processes.sort(key=lambda p: _config_position(p["name"], order))

    return processes

def _config_position(name: str, order: dict[str, int]) -> int:
    slug = name.replace(" ", "_")
    if slug in order:
        return order[slug]
    parts = slug.split("_", 2)
    if len(parts) == 3 and parts[2] in order:
        return order[parts[2]]
    return len(order)

def s6_rescan() -> None:
    _run_cmd(["s6-svscanctl", "-a", S6_SERVICE_DIR], timeout=5, quiet=True)

def s6_svc(flag: str, process_name: str) -> dict:
    svc = _svc_path(process_name)
    if not svc.is_dir():
        return {"status": "error", "message": f"Service {process_name} not found"}
    return _run_cmd(["s6-svc", flag, str(svc)], timeout=10)

def is_process_paused(pid) -> bool:
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:") and "\tT" in line:
                    return True
    except Exception:
        pass
    return False

def pause_process(process_name: str) -> dict:
    result = s6_svc("-p", process_name)

    workdir = Path("/app") / _slug(process_name)
    try:
        subprocess.run(
            ["pkill", "-STOP", "-f", str(workdir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception as exc:
        logger.debug(f"pause_process({process_name}) pkill failed: {exc}")
    if result["status"] == "success":
        return {"status": "success", "message": f"Paused process {process_name}"}
    return {"status": "error", "message": result["message"]}

def resume_process(process_name: str) -> dict:
    result = s6_svc("-c", process_name)
    workdir = Path("/app") / _slug(process_name)
    try:
        subprocess.run(
            ["pkill", "-CONT", "-f", str(workdir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception as exc:
        logger.debug(f"resume_process({process_name}) pkill failed: {exc}")
    if result["status"] == "success":
        return {"status": "success", "message": f"Resumed process {process_name}"}
    return {"status": "error", "message": result["message"]}

async def broadcast_status_update() -> bool:
    try:
        await sio.emit('status_update', {
            "status": "success",
            "processes": _collect_processes(),
            "timestamp": datetime.utcnow().isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"Error broadcasting status update: {str(e)}")
        return False

def _truthy(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in {"true", "yes", "1", "on"}

def _pull_commits_enabled(process_name: str) -> bool:
    project = _find_project_config(process_name)
    if not project:
        return False
    cron = project.get("cron") or {}
    if not isinstance(cron, dict):
        return False
    return _truthy(cron.get("pull_commits"))

def update_process_code(process_name: str) -> None:
    workdir = Path("/app") / _slug(process_name)
    if not workdir.exists():
        logger.warning(f"git pull skipped for {process_name}: no working directory")
        return

    if not _pull_commits_enabled(process_name):
        logger.info(
            f"git pull skipped for {process_name}: pull_commits is not 'true' in project.toml"
        )
        return

    logger.info(f"git pull starting for {process_name} in {workdir}")
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"git pull timed out for {process_name}")
        return
    except Exception as e:
        logger.error(f"git pull failed for {process_name}: {e}")
        return

    for line in (result.stdout or "").splitlines():
        logger.info(f"[git pull {process_name}] {line}")
    for line in (result.stderr or "").splitlines():

        log_fn = logger.info if result.returncode == 0 else logger.error
        log_fn(f"[git pull {process_name}] {line}")

    if result.returncode == 0:
        logger.info(f"git pull finished for {process_name}")
    else:
        logger.error(
            f"git pull for {process_name} exited {result.returncode}"
        )

users = {
    "admin": "password123",
    "newuser": "newpassword"
}

def _dashboard_credentials() -> dict[str, str]:
    creds = dict(users)
    try:
        with CONFIG_FILE.open("rb") as fh:
            raw = tomllib.load(fh)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return creds

    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        return creds

    username = str(defaults.get("username") or "").strip()
    password = str(defaults.get("password") or "")
    if not username or not password:
        return creds

    creds = {username: password}
    return creds

def login_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return await f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({"status": "error", "message": "Not logged in"}), 401
        return await f(*args, **kwargs)
    return decorated_function

async def _dashboard_page(name: str):
    if not (DASHBOARD_DIR / name).is_file():
        return jsonify({
            "status": "error",
            "message": "Dashboard is not built; run `npm ci && npm run build` in web/",
        }), 503
    response = await send_from_directory(DASHBOARD_DIR, name)
    response.headers["Cache-Control"] = "no-cache"
    return response

@app.route('/login')
async def login():
    if 'logged_in' in session:
        return redirect(url_for('cluster'))
    return await _dashboard_page('login.html')

@app.route('/auth/login', methods=['POST'])
async def api_login():
    data = await request.get_json(silent=True) or {}
    username = str(data.get('username') or '')
    password = str(data.get('password') or '')

    creds = _dashboard_credentials()
    if username in creds and creds[username] == password:
        session['logged_in'] = True
        return jsonify({"status": "success"}), 200
    return jsonify({
        "status": "error",
        "message": "Invalid credentials. Please try again.",
    }), 401

@app.route('/logout')
async def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
async def cluster():
    return await _dashboard_page('index.html')

@app.route('/logs')
@login_required
async def logs_page():
    return await _dashboard_page('logs.html')

@app.route('/_next/<path:filename>')
async def dashboard_asset(filename):
    response = await send_from_directory(DASHBOARD_DIR / "_next", filename)
    if filename.startswith("static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response

@app.route('/icon.svg')
async def dashboard_icon():
    return await send_from_directory(DASHBOARD_DIR, 'icon.svg')

@app.route('/service/status', methods=['GET'])
@api_login_required
async def list_service_processes():
    return jsonify({"status": "success", "processes": _collect_processes()}), 200

@app.route('/service/pause/<process_name>', methods=['POST'])
@api_login_required
async def pause_service_process(process_name):
    logger.info(f"Received pause request for process: {process_name}")
    if not _VALID_NAME_RE.match(process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400
    result = pause_process(process_name)
    if result["status"] == "success":
        await broadcast_status_update()
        return jsonify(result), 200
    return jsonify(result), 500

@app.route('/service/resume/<process_name>', methods=['POST'])
@api_login_required
async def resume_service_process(process_name):
    logger.info(f"Received resume request for process: {process_name}")
    if not _VALID_NAME_RE.match(process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400
    result = resume_process(process_name)
    if result["status"] == "success":
        await broadcast_status_update()
        return jsonify(result), 200
    return jsonify(result), 500

def _socket_logged_in(environ: dict) -> bool:
    serializer = app.session_interface.get_signing_serializer(app)
    if serializer is None:
        return False
    cookie_name = app.session_interface.get_cookie_name(app)
    for part in re.split(r"[;,]", environ.get("HTTP_COOKIE", "")):
        key, _, value = part.strip().partition("=")
        if key != cookie_name:
            continue
        try:
            data = serializer.loads(
                value, max_age=int(app.permanent_session_lifetime.total_seconds())
            )
        except BadSignature:
            return False
        return bool(data.get("logged_in"))
    return False

@sio.event
async def connect(sid, environ, auth=None):
    if not _socket_logged_in(environ):
        raise SocketRefused("Not logged in")
    logger.debug(f"Client connected: {sid}")
    await sio.emit('connected', {'data': 'Connected'}, to=sid)
    await broadcast_status_update()

@sio.event
async def disconnect(sid):
    logger.debug(f"Client disconnected: {sid}")

@sio.on('request_status')
async def handle_status_request(sid):
    try:
        processes = _collect_processes()
        if not processes:
            logger.warning("No projects configured and no s6 services found")
        await sio.emit('status_update', {
            "status": "success",
            "processes": processes,
            "timestamp": datetime.utcnow().isoformat()
        }, to=sid)
    except Exception as e:
        logger.error(f"Error in handle_status_request: {str(e)}")
        await sio.emit('status_update', {
            "status": "error",
            "message": str(e),
            "processes": []
        }, to=sid)

def _save_and_unlink_run(process_name: str) -> None:
    run_path = _svc_path(process_name) / "run"
    if run_path.exists():
        STOPPED_SERVICE_SCRIPTS[process_name] = run_path.read_text()
        run_path.unlink()

def _restore_run(process_name: str) -> bool:
    if process_name not in STOPPED_SERVICE_SCRIPTS:
        return False
    run_path = _svc_path(process_name) / "run"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(STOPPED_SERVICE_SCRIPTS[process_name])
    run_path.chmod(0o755)
    del STOPPED_SERVICE_SCRIPTS[process_name]
    return True

async def _wait_for_status(process_name: str, expected: str | None) -> bool:
    for _ in range(MAX_STATUS_CHECK_ATTEMPTS):
        await asyncio.sleep(STATUS_CHECK_INTERVAL)
        parsed = s6_svstat(process_name)
        if expected is None:
            if parsed is None or parsed["status"] != "RUNNING":
                return True
        else:
            if parsed and parsed["status"] == expected:
                return True
    return False

@app.route('/service/<action>/<process_name>', methods=['POST'])
@api_login_required
async def manage_service_process(action, process_name):
    logger.info(f"Received {action} request for process: {process_name}")

    if action not in ("start", "stop", "restart"):
        return jsonify({"status": "error", "message": "Invalid action"}), 400

    if not _VALID_NAME_RE.match(process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400

    parsed = s6_svstat(process_name)
    if parsed is None and action != "start":
        return jsonify({
            "status": "error",
            "message": f"Process {process_name} not found"
        }), 404

    try:
        if action == "stop":
            if parsed["status"] != "RUNNING":
                return jsonify({
                    "status": "error",
                    "message": f"Process {process_name} is not running"
                }), 400

            result = _run_cmd(
                ["s6-svc", "-wD", "-d", str(_svc_path(process_name))],
                timeout=15,
            )
            _kill_orphans(process_name)
            if result["status"] == "success":
                _save_and_unlink_run(process_name)
                s6_rescan()
            expected = None

        elif action == "start":
            if not _restore_run(process_name) and not (_svc_path(process_name) / "run").exists():
                return jsonify({
                    "status": "error",
                    "message": f"Service {process_name} has no run script"
                }), 404
            update_process_code(process_name)
            s6_rescan()
            result = s6_svc("-u", process_name)
            expected = "RUNNING"

        else:
            thoroughly_cleanup(process_name)
            delete_service_logs(process_name)
            update_process_code(process_name)
            result = s6_svc("-r", process_name)
            expected = "RUNNING"

        if result["status"] != "success":
            return jsonify(result), 500

        if await _wait_for_status(process_name, expected):
            await broadcast_status_update()
            if action == "stop":
                msg = f"Successfully stopped {process_name}"
            else:
                msg = f"Successfully {action}ed {process_name}"
            return jsonify({"status": "success", "message": msg}), 200

        return jsonify({
            "status": "error",
            "message": f"Process did not reach expected state after {action}"
        }), 500

    except Exception as e:
        logger.error(f"Error managing process {process_name}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error managing process: {str(e)}"
        }), 500

@app.route('/service/log/<process_name>', methods=['GET'])
@api_login_required
async def download_service_log(process_name):
    try:
        if not _VALID_NAME_RE.match(process_name):
            return jsonify({"status": "error", "message": "Invalid process name"}), 400

        log_file = Path(S6_LOG_DIR) / _slug(process_name) / "current"
        if not log_file.exists():
            return jsonify({
                "status": "error",
                "message": "No log file found for this process"
            }), 404

        try:
            data = log_file.read_bytes()
        except OSError as exc:
            logger.error(f"Error reading log file for {process_name}: {exc}")
            return jsonify({"status": "error", "message": str(exc)}), 500

        download_name = f"{process_name}_log.txt"
        return Response(
            data,
            mimetype="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{download_name}"',
                "Cache-Control": "no-store",
            },
        )

    except Exception as e:
        logger.error(f"Error accessing log file for {process_name}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.errorhandler(Exception)
async def handle_error(e):
    try:
        req_info = f"{request.method} {request.path} from {request.remote_addr}"
        ua = request.headers.get("User-Agent", "")
        if ua:
            req_info += f" ua={ua!r}"
    except Exception:
        req_info = "<no request context>"

    if isinstance(e, HTTPException):
        status = e.code or 500
        if status >= 500:
            logger.error(f"HTTP {status} [{req_info}]: {e}")
        else:
            logger.info(f"HTTP {status} [{req_info}]: {e}")
        return jsonify({
            "status": "error",
            "message": e.description or e.name,
        }), status

    logger.error(f"Unhandled error [{req_info}]: {str(e)}")
    return jsonify({
        "status": "error",
        "message": "An internal server error occurred"
    }), 500

def delete_service_logs(process_name: str) -> None:
    log_svc = _svc_path(process_name) / "log"
    log_svc_active = log_svc.is_dir()
    try:
        if log_svc_active:

            _run_cmd(
                ["s6-svc", "-wD", "-d", str(log_svc)],
                timeout=10,
                quiet=True,
            )
    except Exception as e:
        logger.warning(f"Could not stop log service for {process_name}: {e}")

    try:
        log_dir = Path(S6_LOG_DIR) / _slug(process_name)
        if log_dir.exists():
            for f in log_dir.iterdir():
                try:
                    f.unlink()
                    logger.info(f"Deleted log file: {f}")
                except Exception as e:
                    logger.error(f"Failed to delete {f}: {e}")
    except Exception as e:
        logger.error(f"Error deleting logs for {process_name}: {e}")
    finally:
        if log_svc_active:
            try:

                _run_cmd(["s6-svc", "-u", str(log_svc)], timeout=5, quiet=True)
            except Exception as e:
                logger.warning(
                    f"Could not restart log service for {process_name}: {e}"
                )

def _kill_orphans(process_name: str) -> None:
    slug = _slug(process_name)
    workdir = Path("/app") / slug
    patterns = [str(workdir)]

    for pat in patterns:
        try:
            subprocess.run(
                ["pkill", "-9", "-f", pat],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception as exc:
            logger.debug(f"_kill_orphans({process_name}) pkill {pat} failed: {exc}")

def thoroughly_cleanup(process_name: str) -> None:
    _kill_orphans(process_name)
    workdir = Path("/app") / _slug(process_name)
    if workdir.exists():
        for root, dirs, files in os.walk(workdir):
            for d in dirs:
                if d == '__pycache__':
                    pycache_dir = Path(root) / d
                    for file in pycache_dir.glob('*.pyc'):
                        file.unlink()
                    try:
                        pycache_dir.rmdir()
                    except OSError:
                        pass
            for f in files:
                if f.endswith('.pyc'):
                    (Path(root) / f).unlink()

@app.route('/service/clear_failure/<process_name>', methods=['POST'])
@api_login_required
async def clear_failure(process_name):
    if not _VALID_NAME_RE.match(process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400
    FAILURE_COUNTS[process_name] = 0
    PAUSED_BY_SYSTEM.discard(process_name)
    s6_svc("-u", process_name)
    await broadcast_status_update()
    return jsonify({"status": "success", "message": f"Cleared failure state for {process_name}"})

def _find_project_config(process_name: str) -> dict | None:
    try:
        with CONFIG_FILE.open("rb") as fh:
            raw = tomllib.load(fh)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return None
    projects = raw.get("project") or []
    defaults = raw.get("defaults") or {}
    if not isinstance(projects, list):
        return None
    default_token = (str(defaults.get("access_token") or "")).strip() or None
    for entry in projects:
        if not isinstance(entry, dict):
            continue
        raw_id = str(entry.get("id", "")).strip()
        if not raw_id:
            continue
        if process_name == raw_id or process_name.endswith("_" + raw_id):
            merged = dict(entry)
            merged.setdefault("python_version",
                              entry.get("python_version") or defaults.get("python_version"))
            merged["_raw_id"] = raw_id

            repo_raw = str(entry.get("repo") or "").strip().lower()
            repo_kind = "private" if repo_raw in ("private", "priv") else "public"
            project_token = (str(entry.get("access_token") or "")).strip() or None
            access_token = (
                project_token or default_token if repo_kind == "private" else None
            )
            merged["repo"] = repo_kind
            merged["access_token"] = access_token
            if repo_kind == "private" and not access_token:
                logger.warning(
                    f"Project {raw_id} is repo=\"private\" but has no access_token; "
                    f"redeploy clone will probably fail."
                )
            return merged
    return None

def _redeploy_blocking(process_name: str, project: dict) -> None:
    from git import Repo

    workdir = Path("/app") / _slug(process_name)
    if workdir.exists():
        logger.info(f"Redeploy: removing {workdir}")
        shutil.rmtree(workdir, ignore_errors=True)

    git_url = str(project.get("git_url", "")).strip()
    branch = str(project.get("branch", "main")).strip() or "main"

    try:
        from worker.config_loader import inject_access_token
        clone_url = inject_access_token(git_url, project.get("access_token"))
    except Exception:
        clone_url = git_url

    logger.info(f"Redeploy: cloning {git_url} (branch {branch}) into {workdir}")
    Repo.clone_from(clone_url, str(workdir), branch=branch, single_branch=True)

    requirements_file = workdir / "requirements.txt"
    venv_dir = workdir / "venv"
    python_version = project.get("python_version")

    python_executable = shutil.which("python3") or "python3"
    try:
        from worker.pyenv_utils import get_pyenv_python, run_with_pyenv
        if python_version:
            python_executable = get_pyenv_python(python_version)
    except Exception:
        get_pyenv_python = None
        run_with_pyenv = None

    if not requirements_file.exists():
        logger.info("Redeploy: no requirements.txt, skipping venv build")
        return

    venv_cmd = ["uv", "venv", str(venv_dir), "--python", str(python_executable)]
    pip_cmd = [
        "uv", "pip", "install", "--no-cache",
        "--python", str(venv_dir / "bin" / "python"),
        "-r", str(requirements_file),
    ]
    logger.info(f"Redeploy: creating venv {venv_dir}")
    if python_version and run_with_pyenv is not None:
        run_with_pyenv(python_version, venv_cmd, check=True)
        run_with_pyenv(python_version, pip_cmd, check=True)
    else:
        subprocess.run(venv_cmd, check=True)
        subprocess.run(pip_cmd, check=True)

@app.route('/service/redeploy/<process_name>', methods=['POST'])
@api_login_required
async def redeploy_service(process_name):
    logger.info(f"Received redeploy request for process: {process_name}")
    if not _VALID_NAME_RE.match(process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400

    parsed = s6_svstat(process_name)
    if parsed is None:
        return jsonify({"status": "error", "message": f"Service {process_name} not found"}), 404

    project = _find_project_config(process_name)
    if project is None:
        return jsonify({
            "status": "error",
            "message": f"No project.toml entry matches {process_name}",
        }), 404

    try:

        _run_cmd(
            ["s6-svc", "-wD", "-d", str(_svc_path(process_name))],
            timeout=15,
        )
        _kill_orphans(process_name)
        await _wait_for_status(process_name, None)

        await asyncio.get_event_loop().run_in_executor(
            None, _redeploy_blocking, process_name, project
        )

        FAILURE_COUNTS[process_name] = 0
        PAUSED_BY_SYSTEM.discard(process_name)
        delete_service_logs(process_name)
        s6_rescan()
        result = s6_svc("-u", process_name)
        if result["status"] != "success":
            return jsonify(result), 500

        if await _wait_for_status(process_name, "RUNNING"):
            await broadcast_status_update()
            return jsonify({
                "status": "success",
                "message": f"Redeployed {process_name}",
            }), 200
        return jsonify({
            "status": "error",
            "message": "Service did not reach RUNNING state after redeploy",
        }), 500
    except Exception as e:
        logger.exception(f"Redeploy failed for {process_name}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/service/stream-view/<process_name>')
@login_required
async def stream_log_page(process_name):
    if not _VALID_NAME_RE.match(process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400
    return redirect(url_for('logs_page', name=process_name))

@app.route('/service/stream/<process_name>')
@api_login_required
async def stream_service_log(process_name):
    if not _VALID_NAME_RE.match(process_name):
        return jsonify({"status": "error", "message": "Invalid process name"}), 400

    log_file = Path(S6_LOG_DIR) / _slug(process_name) / "current"

    async def _tail():

        yield f"data: [stream] connected to {process_name}\n\n"
        if not log_file.exists():
            yield f"data: [stream] waiting for {log_file} to appear…\n\n"
        else:
            yield f"data: [stream] tailing {log_file}\n\n"

        fh = None
        inode = None
        try:
            while True:
                try:
                    if not log_file.exists():
                        if fh is not None:
                            try:
                                fh.close()
                            except Exception:
                                pass
                            fh = None
                            inode = None
                        await asyncio.sleep(1.0)

                        yield ": waiting-for-log\n\n"
                        continue

                    st = log_file.stat()
                    if fh is None or inode != st.st_ino:

                        if fh is not None:
                            try:
                                fh.close()
                            except Exception:
                                pass
                        fh = log_file.open("r", encoding="utf-8", errors="replace")
                        fh.seek(0, os.SEEK_END)
                        inode = st.st_ino

                    chunk = fh.read()
                    if chunk:
                        for line in chunk.splitlines():
                            yield f"data: {line}\n\n"
                    else:

                        yield ": ping\n\n"
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(
                        f"stream_service_log({process_name}) tail error: {exc}"
                    )
                    yield f"data: [stream] error: {exc}\n\n"
                    if fh is not None:
                        try:
                            fh.close()
                        except Exception:
                            pass
                        fh = None
                        inode = None
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return
        finally:
            if fh is not None:
                try:
                    fh.close()
                except Exception:
                    pass

    headers = {

        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(_tail(), headers=headers, mimetype="text/event-stream")
