"""Offline contract tests for the non-template backup systemd units (C5, D36)."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "infra" / "systemd"
SERVICE = UNITS / "proxima-pg-backup.service"
TIMER = UNITS / "proxima-pg-backup.timer"
SCRIPT = ROOT / "infra" / "backup" / "proxima-pg-backup.sh"


def section_values(unit: Path, section: str, key: str) -> list[str]:
    values: list[str] = []
    in_section = False
    for line in unit.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            continue
        if in_section and not stripped.startswith(("#", ";")) and "=" in stripped:
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                values.append(value.strip())
    return values


def test_backup_units_exist_and_are_not_templates() -> None:
    assert SERVICE.is_file()
    assert TIMER.is_file()
    assert "@" not in SERVICE.name
    assert "@" not in TIMER.name


def test_backup_timer_runs_at_0300_moscow_and_is_persistent() -> None:
    assert section_values(TIMER, "Timer", "OnCalendar") == [
        "*-*-* 03:00:00 Europe/Moscow"
    ]
    assert section_values(TIMER, "Timer", "Persistent") == ["true"]
    assert section_values(TIMER, "Timer", "RandomizedDelaySec") == []


def test_backup_service_contract() -> None:
    assert section_values(SERVICE, "Service", "ExecStart") == [
        "/usr/local/bin/proxima-pg-backup.sh"
    ]
    assert section_values(SERVICE, "Service", "Environment") == [
        "PROXIMA_RAW_DIR=/srv/proxima-ai/raw"
    ]
    assert section_values(SERVICE, "Unit", "OnFailure") == [
        "proxima-alert@%n.service"
    ]


def test_backup_script_checks_raw_dir_and_has_valid_bash_syntax() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert '[[ -n "${PROXIMA_RAW_DIR:-}" ]]' in script
    assert 'fail "PROXIMA_RAW_DIR is required"' in script
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
