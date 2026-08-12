from __future__ import annotations

import json
import math
import os
import socket
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT_PATH = Path("/etc/proxima-ai/vps-contract.json")
DEFAULT_STATE_PATH = Path("/var/lib/proxima-ai-monitor/state.json")
HISTORY_LIMIT = 60


@dataclass(frozen=True)
class CpuTicks:
    total: int
    idle: int

    @classmethod
    def from_mapping(cls, value: object) -> CpuTicks | None:
        if not isinstance(value, dict):
            return None
        total = value.get("total")
        idle = value.get("idle")
        if not isinstance(total, int) or not isinstance(idle, int):
            return None
        return cls(total=total, idle=idle)


@dataclass(frozen=True)
class MetricSnapshot:
    observed_at: str
    cpu_percent: float
    memory_available_percent: float
    disk_used_percent: float

    @classmethod
    def from_mapping(cls, value: object) -> MetricSnapshot | None:
        if not isinstance(value, dict):
            return None
        observed_at = value.get("observed_at")
        metrics = (value.get("cpu_percent"), value.get("memory_available_percent"), value.get("disk_used_percent"))
        if not isinstance(observed_at, str) or not all(isinstance(metric, int | float) for metric in metrics):
            return None
        return cls(
            observed_at=observed_at,
            cpu_percent=float(metrics[0]),
            memory_available_percent=float(metrics[1]),
            disk_used_percent=float(metrics[2]),
        )


@dataclass(frozen=True)
class Thresholds:
    cpu_warning: float
    cpu_urgent: float
    memory_warning_below: float
    memory_urgent_below: float
    disk_warning: float
    disk_resize_recommendation: float
    disk_urgent: float

    @classmethod
    def from_contract(cls, contract: dict[str, Any]) -> Thresholds:
        thresholds = contract["monitoring"]["thresholds"]
        cpu = thresholds["cpu_percent"]
        memory = thresholds["memory_available_percent"]
        disk = thresholds["disk_used_percent"]
        return cls(
            cpu_warning=float(cpu["warning"]),
            cpu_urgent=float(cpu["urgent"]),
            memory_warning_below=float(memory["warning_below"]),
            memory_urgent_below=float(memory["urgent_below"]),
            disk_warning=float(disk["warning"]),
            disk_resize_recommendation=float(disk["resize_recommendation"]),
            disk_urgent=float(disk["urgent"]),
        )


@dataclass(frozen=True)
class Alert:
    metric: str
    severity: str
    value: float
    threshold: float
    action: str


@dataclass(frozen=True)
class Notification:
    kind: str
    metric: str
    severity: str
    value: float | None = None
    threshold: float | None = None
    action: str | None = None


def required_samples(contract: dict[str, Any]) -> int:
    monitoring = contract["monitoring"]
    interval = int(monitoring["interval_seconds"])
    sustained = int(monitoring["sustained_seconds"])
    if interval <= 0 or sustained <= 0:
        raise ValueError("monitor interval and sustained duration must be positive")
    return max(2, math.ceil(sustained / interval) + 1)


def observed_at(value: str) -> datetime | None:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        return None
    return timestamp.astimezone(UTC)


def sustained_window(history: list[MetricSnapshot], sustained_seconds: int, interval_seconds: int) -> list[MetricSnapshot] | None:
    required = math.ceil(sustained_seconds / interval_seconds) + 1
    window = history[-required:]
    if len(window) != required:
        return None

    timestamps = [observed_at(sample.observed_at) for sample in window]
    if any(timestamp is None for timestamp in timestamps):
        return None
    resolved = [timestamp for timestamp in timestamps if timestamp is not None]
    if (resolved[-1] - resolved[0]).total_seconds() < sustained_seconds:
        return None
    max_gap_seconds = interval_seconds * 2
    if any(not 0 < (later - earlier).total_seconds() <= max_gap_seconds for earlier, later in zip(resolved, resolved[1:])):
        return None
    return window


def classify(history: list[MetricSnapshot], thresholds: Thresholds, sustained_seconds: int, interval_seconds: int) -> list[Alert]:
    if not history:
        return []

    latest = history[-1]
    alerts: list[Alert] = []
    window = sustained_window(history, sustained_seconds, interval_seconds)
    if window is not None:
        if all(sample.cpu_percent > thresholds.cpu_urgent for sample in window):
            alerts.append(Alert("cpu_percent", "urgent", latest.cpu_percent, thresholds.cpu_urgent, "request manual capacity increase; do not resize automatically"))
        elif all(sample.cpu_percent > thresholds.cpu_warning for sample in window):
            alerts.append(Alert("cpu_percent", "warning", latest.cpu_percent, thresholds.cpu_warning, "review workload and prepare manual capacity decision"))

        if all(sample.memory_available_percent < thresholds.memory_urgent_below for sample in window):
            alerts.append(Alert("memory_available_percent", "urgent", latest.memory_available_percent, thresholds.memory_urgent_below, "pause non-essential jobs and request manual capacity increase"))
        elif all(sample.memory_available_percent < thresholds.memory_warning_below for sample in window):
            alerts.append(Alert("memory_available_percent", "warning", latest.memory_available_percent, thresholds.memory_warning_below, "review memory use and prepare manual capacity decision"))

    if latest.disk_used_percent > thresholds.disk_urgent:
        alerts.append(Alert("disk_used_percent", "urgent", latest.disk_used_percent, thresholds.disk_urgent, "stop non-essential writes and request manual disk increase"))
    elif latest.disk_used_percent > thresholds.disk_resize_recommendation:
        alerts.append(Alert("disk_used_percent", "resize_recommendation", latest.disk_used_percent, thresholds.disk_resize_recommendation, "request a manual disk increase in an agreed change window"))
    elif latest.disk_used_percent > thresholds.disk_warning:
        alerts.append(Alert("disk_used_percent", "warning", latest.disk_used_percent, thresholds.disk_warning, "review storage growth and prepare a manual capacity decision"))
    return alerts


def read_cpu_ticks() -> CpuTicks:
    for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines():
        if line.startswith("cpu "):
            fields = [int(item) for item in line.split()[1:]]
            if len(fields) < 5:
                break
            return CpuTicks(total=sum(fields), idle=fields[3] + fields[4])
    raise RuntimeError("unable to read CPU counters")


def cpu_percent(current: CpuTicks, previous: CpuTicks | None) -> float:
    if previous is None or current.total <= previous.total:
        return 0.0
    total_delta = current.total - previous.total
    idle_delta = max(0, current.idle - previous.idle)
    return round(max(0.0, min(100.0, 100.0 * (1 - idle_delta / total_delta))), 2)


def memory_available_percent() -> float:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        name, raw_value = line.split(":", maxsplit=1)
        values[name] = int(raw_value.split()[0])
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        raise RuntimeError("unable to read memory counters")
    return round(100.0 * available / total, 2)


def disk_used_percent() -> float:
    stats = os.statvfs("/")
    if stats.f_blocks <= 0:
        raise RuntimeError("unable to read disk counters")
    used_blocks = stats.f_blocks - stats.f_bavail
    return round(100.0 * used_blocks / stats.f_blocks, 2)


def collect_snapshot(previous_ticks: CpuTicks | None) -> tuple[MetricSnapshot, CpuTicks]:
    current_ticks = read_cpu_ticks()
    return (
        MetricSnapshot(
            observed_at=datetime.now(UTC).isoformat(),
            cpu_percent=cpu_percent(current_ticks, previous_ticks),
            memory_available_percent=memory_available_percent(),
            disk_used_percent=disk_used_percent(),
        ),
        current_ticks,
    )


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"history": [], "active": {}, "previous_cpu_ticks": None}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"history": [], "active": {}, "previous_cpu_ticks": None}
    if not isinstance(value, dict):
        return {"history": [], "active": {}, "previous_cpu_ticks": None}
    return value


def load_history(state: dict[str, Any]) -> list[MetricSnapshot]:
    raw_history = state.get("history")
    if not isinstance(raw_history, list):
        return []
    snapshots = [MetricSnapshot.from_mapping(item) for item in raw_history]
    return [snapshot for snapshot in snapshots if snapshot is not None][-HISTORY_LIMIT:]


def load_active(state: dict[str, Any]) -> dict[str, str]:
    raw_active = state.get("active")
    if not isinstance(raw_active, dict):
        return {}
    return {metric: severity for metric, severity in raw_active.items() if isinstance(metric, str) and isinstance(severity, str)}


def write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fchmod(handle.fileno(), 0o600)
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def desired_active(alerts: list[Alert]) -> dict[str, str]:
    return {alert.metric: alert.severity for alert in alerts}


def notification_events(previous: dict[str, str], alerts: list[Alert]) -> list[Notification]:
    current = desired_active(alerts)
    by_metric = {alert.metric: alert for alert in alerts}
    events: list[Notification] = []
    for metric, alert in by_metric.items():
        if previous.get(metric) != alert.severity:
            events.append(Notification("alert", metric, alert.severity, alert.value, alert.threshold, alert.action))
    for metric, severity in previous.items():
        if metric not in current:
            events.append(Notification("recovery", metric, severity))
    return sorted(events, key=lambda event: (event.metric, event.kind))


def format_notification(event: Notification) -> str:
    hostname = socket.gethostname()
    if event.kind == "recovery":
        return "\n".join(
            [
                "PROXIMA host capacity recovered",
                f"host={hostname}",
                f"metric={event.metric}",
                f"previous_severity={event.severity}",
            ]
        )
    assert event.value is not None and event.threshold is not None and event.action is not None
    return "\n".join(
        [
            "PROXIMA host capacity alert",
            f"host={hostname}",
            f"metric={event.metric}",
            f"severity={event.severity}",
            f"value={event.value:.2f}",
            f"threshold={event.threshold:.2f}",
            f"action={event.action}",
        ]
    )


def read_secret(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def main() -> int:
    contract_path = Path(os.environ.get("PROXIMA_MONITOR_CONTRACT", DEFAULT_CONTRACT_PATH))
    state_path = Path(os.environ.get("PROXIMA_MONITOR_STATE_FILE", DEFAULT_STATE_PATH))
    token_path = Path(os.environ.get("PROXIMA_TELEGRAM_TOKEN_FILE", "/etc/proxima-ai/secrets/telegram_bot_token"))
    chat_path = Path(os.environ.get("PROXIMA_TELEGRAM_CHAT_ID_FILE", "/etc/proxima-ai/secrets/telegram_chat_id"))

    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        thresholds = Thresholds.from_contract(contract)
        required_samples(contract)
        sustained_seconds = int(contract["monitoring"]["sustained_seconds"])
        interval_seconds = int(contract["monitoring"]["interval_seconds"])
        state = load_state(state_path)
        previous_ticks = CpuTicks.from_mapping(state.get("previous_cpu_ticks"))
        snapshot, current_ticks = collect_snapshot(previous_ticks)
    except (OSError, TypeError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(f"host monitor failed safely: {error.__class__.__name__}", file=sys.stderr)
        return 1

    history = (load_history(state) + [snapshot])[-HISTORY_LIMIT:]
    alerts = classify(history, thresholds, sustained_seconds, interval_seconds)
    previous_active = load_active(state)
    events = notification_events(previous_active, alerts)
    token = read_secret(token_path)
    chat_id = read_secret(chat_path)
    current_active = desired_active(alerts)

    active = previous_active
    if not events:
        active = current_active
    elif token is not None and chat_id is not None:
        delivery_ok = all(send_telegram(token, chat_id, format_notification(event)) for event in events)
        if delivery_ok:
            active = current_active
        else:
            print("host monitor: Telegram delivery failed; alert state retained", file=sys.stderr)
    else:
        print("host monitor: Telegram secret files are unavailable; alert state retained", file=sys.stderr)

    write_state(
        state_path,
        {
            "active": active,
            "history": [asdict(item) for item in history],
            "previous_cpu_ticks": asdict(current_ticks),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
