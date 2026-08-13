from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def mapping(value: object, path: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{path}: expected object")
    return {}


def verify(root: Path = ROOT) -> None:
    errors: list[str] = []
    contract_path = root / "infra" / "vps-contract.json"
    contract = mapping(json.loads(contract_path.read_text(encoding="utf-8")), "infra/vps-contract.json", errors)

    decision = mapping(contract.get("decision"), "decision", errors)
    require(decision.get("provider") == "Selectel Cloud", "decision.provider must be Selectel Cloud", errors)
    require(decision.get("region") == "Russia", "decision.region must be Russia", errors)
    require(decision.get("stage") == "staging_then_pilot", "decision.stage must be staging_then_pilot", errors)

    baseline = mapping(contract.get("baseline"), "baseline", errors)
    storage = mapping(baseline.get("storage"), "baseline.storage", errors)
    require(decision.get("host_ipv4") == "135.106.186.210", "decision.host_ipv4 must match the approved host", errors)
    require(decision.get("retain_observed_host") is True, "observed host retention must be approved", errors)
    require(baseline.get("vcpus") == 6, "baseline.vcpus must match observed host", errors)
    require(baseline.get("memory_gib") == 12, "baseline.memory_gib must match observed host class", errors)
    require(storage.get("kind") == "nvme" and storage.get("gib") == 120, "baseline.storage must match observed 120 GiB NVMe class", errors)
    require(baseline.get("operating_system") == "ubuntu-24.04-lts", "baseline.operating_system must be ubuntu-24.04-lts", errors)
    require(baseline.get("observed_memory_kib") == 12247548, "observed memory evidence must be retained", errors)
    require(baseline.get("observed_root_filesystem_bytes") == 126752366592, "observed disk evidence must be retained", errors)
    require(baseline.get("monthly_budget_rub") == 3000, "baseline.monthly_budget_rub must be 3000", errors)
    require(baseline.get("monthly_price_rub") is None, "unknown monthly price must not be invented", errors)
    require(baseline.get("price_verification") == "pending_selectel_billing", "Selectel price verification must remain explicit", errors)

    network = mapping(contract.get("network"), "network", errors)
    security_group = mapping(network.get("security_group"), "network.security_group", errors)
    require(security_group.get("inbound_allow") == ["tcp/22"], "security group must allow only TCP/22 inbound", errors)
    require(security_group.get("application_public_ports") == [], "application public ports must be empty", errors)
    require(network.get("application_access") == "ssh_tunnel_only", "application access must be SSH tunnel only", errors)

    access = mapping(contract.get("access"), "access", errors)
    require(access.get("admin_user") == "proxima-admin", "access.admin_user must be proxima-admin", errors)
    require(access.get("ssh_key_only") is True, "access.ssh_key_only must be true", errors)
    require(access.get("root_login") is False, "access.root_login must be false", errors)
    require(access.get("password_authentication") is False, "access.password_authentication must be false", errors)

    paths = mapping(contract.get("paths"), "paths", errors)
    for name in ("repository", "raw_store", "monitor_state", "secrets"):
        value = paths.get(name)
        require(isinstance(value, str) and value.startswith("/") and not value.startswith(str(root)), f"paths.{name} must be an absolute host path outside the repository", errors)

    monitoring = mapping(contract.get("monitoring"), "monitoring", errors)
    thresholds = mapping(monitoring.get("thresholds"), "monitoring.thresholds", errors)
    cpu = mapping(thresholds.get("cpu_percent"), "monitoring.thresholds.cpu_percent", errors)
    memory = mapping(thresholds.get("memory_available_percent"), "monitoring.thresholds.memory_available_percent", errors)
    disk = mapping(thresholds.get("disk_used_percent"), "monitoring.thresholds.disk_used_percent", errors)
    require(monitoring.get("channel") == "private_telegram_chat", "monitoring.channel must be private Telegram chat", errors)
    require(monitoring.get("interval_seconds") == 60, "monitor interval must be 60 seconds", errors)
    require(monitoring.get("sustained_seconds") == 900, "sustained duration must be 900 seconds", errors)
    require(cpu.get("warning") == 70 and cpu.get("urgent") == 85, "CPU thresholds must be 70/85", errors)
    require(memory.get("warning_below") == 20 and memory.get("urgent_below") == 10, "memory thresholds must be 20/10", errors)
    require(
        disk.get("warning") == 70 and disk.get("resize_recommendation") == 80 and disk.get("urgent") == 90,
        "disk thresholds must be 70/80/90",
        errors,
    )

    scaling = mapping(contract.get("scaling"), "scaling", errors)
    require(scaling.get("automatic") is False, "automatic scaling must be disabled", errors)
    require(scaling.get("action") == "recommend_only", "scaling action must be recommend_only", errors)
    require(scaling.get("approval") == "Mike", "scaling approval must be Mike", errors)
    require(scaling.get("change_window") == "manual_agreed", "scaling change window must be manual_agreed", errors)

    data_admission = mapping(contract.get("business_data_admission"), "business_data_admission", errors)
    require(data_admission.get("allowed_now") is False, "business data must remain blocked before backup guardrail", errors)
    require(data_admission.get("requires_backup_guardrail") is True, "backup guardrail must be required", errors)
    require(data_admission.get("full_recovery_ownership_phase") == 7, "full recovery must remain Phase 7", errors)

    bootstrap = (root / "infra" / "bootstrap" / "bootstrap-vps.sh").read_text(encoding="utf-8")
    for required in (
        "PROXIMA_SECURITY_GROUP_VERIFIED",
        "PermitRootLogin no",
        "PasswordAuthentication no",
        "ufw default deny incoming",
        "git clone --no-hardlinks",
        "remote remove bootstrap-source",
        "runuser --user",
        "NOPASSWD: ALL",
        "visudo --check",
        "passwd --lock root",
        "systemctl enable --now docker",
        "Do not enable proxima-host-monitor.timer before Telegram secret files",
    ):
        require(required in bootstrap or required in (root / "infra" / "bootstrap" / "60-proxima-ai.conf").read_text(encoding="utf-8"), f"bootstrap boundary missing: {required}", errors)

    day1_runtime = (root / "infra" / "bootstrap" / "prepare-day1-runtime.sh").read_text(encoding="utf-8")
    for required in (
        "Python 3.11+ is required",
        "/etc/proxima-ai/secrets",
        "WB_STATISTICS_TOKEN_FILE=",
        "PROXIMA_RAW_DIR=",
        "tools/wb_api_probe_requirements.txt",
        "docker compose",
        "up --detach postgres",
        '"healthy"',
    ):
        require(required in day1_runtime, f"Day 1 runtime boundary missing: {required}", errors)
    require("WB_API_KEY=" not in day1_runtime, "Day 1 runtime must not put a WB token value in .env", errors)

    runtime_template = (root / "infra" / "runtime.env.template").read_text(encoding="utf-8")
    require(
        runtime_template.splitlines() == [
            "# Copy to repository-root .env. Never put a token value in this file.",
            "WB_STATISTICS_TOKEN_FILE=/etc/proxima-ai/secrets/wb_statistics_token",
            "PROXIMA_RAW_DIR=/srv/proxima-ai/data/day1-wb-api",
        ],
        "runtime env template must contain only path references",
        errors,
    )

    service = (root / "infra" / "monitoring" / "proxima-host-monitor.service").read_text(encoding="utf-8")
    for required in ("User=proxima-monitor", "ProtectSystem=strict", "NoNewPrivileges=true", "ReadWritePaths=/var/lib/proxima-ai-monitor"):
        require(required in service, f"monitor service boundary missing: {required}", errors)

    monitor_env = (root / "infra" / "monitoring" / "monitor.env.example").read_text(encoding="utf-8")
    require("PROXIMA_MONITOR_CONTRACT=/etc/proxima-ai/vps-contract.json" in monitor_env, "monitor contract must be readable outside the private repository", errors)

    monitor = (root / "infra" / "monitoring" / "host_monitor.py").read_text(encoding="utf-8")
    for required in ("def classify", "def sustained_window", "def send_telegram", "os.replace", "request manual capacity increase", "do not resize automatically"):
        require(required in monitor, f"host monitor behavior missing: {required}", errors)

    if errors:
        raise ValueError("VPS contract violations:\n" + "\n".join(sorted(errors)))


if __name__ == "__main__":
    verify()
    print("VPS contract verification passed")
