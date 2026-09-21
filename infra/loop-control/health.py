#!/usr/bin/python3
"""Sanitized LOOP liveness, backup-age and disk check."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import urllib.request

os.umask(0o077)
OUTPUT = Path("/var/lib/loop/health/status.json")
EXPECTED_CONTAINERS = [
    "loop-control-postgres-1", "loop-control-paperclip-1",
    "loop-control-hermes-1", "loop-control-bridge-1",
]
BACKUP_ROOT = Path("/var/backups/loop/daily")
BACKUP_KEY = Path("/etc/loop/secrets/backup_encryption")


def write(value: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(OUTPUT)


def unit_active(name: str) -> bool:
    return subprocess.run(["systemctl", "is-active", "--quiet", name]).returncode == 0


def unit_state(name: str) -> dict[str, object]:
    result = subprocess.run(
        ["systemctl", "show", name, "--property=ActiveState,SubState,Result,ExecMainStatus"],
        capture_output=True, text=True,
    )
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return {
        "loaded": result.returncode == 0,
        "active_state": values.get("ActiveState"),
        "sub_state": values.get("SubState"),
        "result": values.get("Result"),
        "exit_status": int(values.get("ExecMainStatus", "-1")),
    }


def container_running(name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", name],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def http_json(url: str, secret_path: str | None = None) -> dict:
    headers = {}
    if secret_path:
        headers["Authorization"] = "Bearer " + Path(secret_path).read_text().strip()
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)


def verify_backup_artifact(receipt: dict, expected_uid: int = 0) -> bool:
    raw = receipt.get("encrypted_file")
    if not isinstance(raw, str):
        return False
    candidate = Path(raw)
    try:
        relative = candidate.relative_to(BACKUP_ROOT)
    except ValueError:
        return False
    if not relative.parts or any(value in {"", ".", ".."} for value in relative.parts):
        return False
    key_info = BACKUP_KEY.lstat()
    if not stat.S_ISREG(key_info.st_mode) or key_info.st_uid != expected_uid or stat.S_IMODE(key_info.st_mode) != 0o600:
        return False
    key = BACKUP_KEY.read_bytes()
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(BACKUP_ROOT, directory_flags)
    file_descriptor = None
    try:
        root_info = os.fstat(descriptor)
        if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != expected_uid or root_info.st_mode & 0o022:
            return False
        for component in relative.parts[:-1]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            info = os.fstat(next_descriptor)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != expected_uid or info.st_mode & 0o022:
                os.close(next_descriptor)
                return False
            os.close(descriptor)
            descriptor = next_descriptor
        file_descriptor = os.open(relative.parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
        info = os.fstat(file_descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != expected_uid
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size != receipt.get("encrypted_bytes")
        ):
            return False
        digest = hashlib.sha256()
        keyed = hmac.new(key, digestmod=hashlib.sha256)
        while chunk := os.read(file_descriptor, 1024 * 1024):
            digest.update(chunk)
            keyed.update(chunk)
        return hmac.compare_digest(digest.hexdigest(), str(receipt.get("sha256", ""))) and hmac.compare_digest(
            keyed.hexdigest(), str(receipt.get("hmac_sha256", ""))
        )
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        os.close(descriptor)


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    disk = shutil.disk_usage("/var/lib/loop")
    checks: dict[str, object] = {
        "disk_free_bytes": disk.free,
        "disk_floor_bytes": 5 * 1024**3,
        "containers": {name: container_running(name) for name in EXPECTED_CONTAINERS},
        "systemd": {
            name: unit_active(name) for name in [
                "loop-egress-tunnel.service", "loop-egress-proxy.service",
                "loop-openhands-tunnel.service", "loop-openhands-relay.service",
            ]
        },
    }
    errors = []
    try:
        network = subprocess.run(
            ["/usr/local/sbin/loop-network-preflight", "--check"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        checks["private_networks"] = network.returncode == 0
    except Exception as error:
        checks["private_networks"] = False
        errors.append({"component": "private_networks", "error_type": type(error).__name__})
    try:
        checks["paperclip"] = http_json("http://127.0.0.1:3100/api/health").get("status") == "ok"
    except Exception as error:
        checks["paperclip"] = False
        errors.append({"component": "paperclip", "error_type": type(error).__name__})
    try:
        checks["bridge"] = http_json(
            "http://127.0.0.1:18770/v1/status", "/etc/loop/secrets/bridge_operator"
        ).get("scheduler") == "paperclip"
    except Exception as error:
        checks["bridge"] = False
        errors.append({"component": "bridge", "error_type": type(error).__name__})
    try:
        inspect = subprocess.run(
            ["docker", "inspect", "--format", "{{(index .NetworkSettings.Networks \"loop-hermes-private\").IPAddress}}",
             "loop-control-hermes-1"], capture_output=True, text=True, check=True,
        )
        hermes_ip = inspect.stdout.strip()
        checks["hermes"] = http_json(
            f"http://{hermes_ip}:8642/health", "/etc/loop/secrets/hermes_api"
        ).get("status") == "ok"
    except Exception as error:
        checks["hermes"] = False
        errors.append({"component": "hermes", "error_type": type(error).__name__})
    try:
        probe = subprocess.run([
            "docker", "exec", "loop-control-bridge-1", "python3", "-c",
            "import urllib.request;from pathlib import Path;key=Path('/run/secrets/openhands_api').read_text().strip();request=urllib.request.Request('http://127.0.0.1:18000/api/conversations/count',headers={'X-Session-API-Key':key});response=urllib.request.urlopen(request,timeout=8);raise SystemExit(0 if response.status==200 else 1)",
        ], capture_output=True, timeout=12)
        checks["openhands"] = probe.returncode == 0
    except Exception as error:
        checks["openhands"] = False
        errors.append({"component": "openhands", "error_type": type(error).__name__})

    telegram_config = Path("/etc/loop/telegram.json")
    if telegram_config.is_file():
        try:
            running = container_running("loop-control-telegram-1")
            probe = subprocess.run([
                "docker", "exec", "loop-control-telegram-1", "python3", "-c",
                "import json,urllib.request;from pathlib import Path;token=Path('/run/secrets/telegram_bot').read_text().strip();response=json.load(urllib.request.urlopen('https://api.telegram.org/bot'+token+'/getMe',timeout=8));raise SystemExit(0 if response.get('ok') is True else 1)",
            ], capture_output=True, timeout=12)
            checks["telegram"] = {"status": "ready" if running and probe.returncode == 0 else "error", "container": running, "get_me": probe.returncode == 0}
        except Exception as error:
            checks["telegram"] = {"status": "error", "container": False, "get_me": False}
            errors.append({"component": "telegram", "error_type": type(error).__name__})
    else:
        stale_running = container_running("loop-control-telegram-1")
        checks["telegram"] = {"status": "error" if stale_running else "not_configured", "container": stale_running}
        if stale_running:errors.append({"component":"telegram","error_type":"StaleUnconfiguredContainer"})

    backup_attempt_path = Path("/var/lib/loop/backups/status.json")
    backup_success_path = Path("/var/lib/loop/backups/last-success.json")
    try:
        attempt = json.loads(backup_attempt_path.read_text()) if backup_attempt_path.is_file() else {"status": "missing"}
        backup_service = unit_state("loop-backup.service")
        attempt_started = dt.datetime.fromisoformat(attempt["started_at_utc"]) if attempt.get("started_at_utc") else None
        running_age = int((now - attempt_started).total_seconds()) if attempt_started else None
        if backup_success_path.is_file():
            backup = json.loads(backup_success_path.read_text())
            finished = dt.datetime.fromisoformat(backup["finished_at_utc"])
            artifact_verified = verify_backup_artifact(backup)
            checks["backup"] = {
                "latest_attempt_status": attempt.get("status"),
                "last_success_status": backup.get("status"),
                "age_seconds": int((now - finished).total_seconds()),
                "maximum_age_seconds": 36 * 3600,
                "running_age_seconds": running_age,
                "maximum_running_seconds": 21 * 60,
                "service": backup_service,
                "artifact_verified": artifact_verified,
            }
        else:
            checks["backup"] = {
                "latest_attempt_status": attempt.get("status"), "last_success_status": "missing",
                "running_age_seconds": running_age, "maximum_running_seconds": 21 * 60,
                "service": backup_service,
            }
    except Exception as error:
        checks["backup"] = {"latest_attempt_status": "invalid", "last_success_status": "invalid"}
        errors.append({"component": "backup", "error_type": type(error).__name__})

    healthy = (
        disk.free >= checks["disk_floor_bytes"]
        and all(checks["containers"].values())
        and all(checks["systemd"].values())
        and checks.get("private_networks") is True
        and checks.get("telegram", {}).get("status") in {"ready", "not_configured"}
        and all(checks.get(name) is True for name in ["paperclip", "bridge", "hermes", "openhands"])
        and checks["backup"].get("last_success_status") == "ok"
        and checks["backup"].get("latest_attempt_status") in {"ok", "running"}
        and (
            checks["backup"].get("latest_attempt_status") == "ok"
            or (
                checks["backup"].get("running_age_seconds", 10**9)
                <= checks["backup"].get("maximum_running_seconds", 0)
                and checks["backup"].get("service", {}).get("active_state") == "activating"
            )
        )
        and (
            checks["backup"].get("latest_attempt_status") == "running"
            or (
                checks["backup"].get("service", {}).get("result") == "success"
                and checks["backup"].get("service", {}).get("exit_status") == 0
            )
        )
        and checks["backup"].get("age_seconds", 10**9) <= checks["backup"].get("maximum_age_seconds", 0)
        and checks["backup"].get("artifact_verified") is True
    )
    result = {
        "checked_at_utc": now.isoformat(), "status": "ok" if healthy else "error",
        "checks": checks, "errors": errors,
    }
    write(result)
    raise SystemExit(0 if healthy else 1)


if __name__ == "__main__":
    main()
