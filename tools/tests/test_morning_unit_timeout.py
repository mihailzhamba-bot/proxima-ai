"""Offline tests for infra/systemd/proxima-morning@.service (PA-65).

The 06:30 MSK deadline (FR-22) is carried by the unit's TimeoutStartSec:
the timer fires 05:30 MSK, so the start timeout must stay inside 60 minutes
while remaining tight enough to alert in time.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "infra" / "systemd"
MORNING = UNITS / "proxima-morning@.service"


def unit_lines(unit: Path) -> list[str]:
    return unit.read_text(encoding="utf-8").splitlines()


def service_section_values(unit: Path, section: str, key: str) -> list[str]:
    """Values of `key` inside `section` (e.g. '[Service]'), skipping comments."""
    values: list[str] = []
    in_section = False
    for line in unit_lines(unit):
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            continue
        if in_section and not stripped.startswith(("#", ";")) and "=" in stripped:
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                values.append(value.strip())
    return values


def parse_seconds(spec: str) -> int:
    match = re.fullmatch(r"(\d+)\s*(min|s|ms)?", spec)
    assert match is not None, f"unsupported time span: {spec}"
    amount = int(match.group(1))
    suffix = match.group(2) or "s"
    return amount * {"min": 60, "s": 1, "ms": 0}[suffix]


def test_morning_unit_carries_the_deadline_timeout() -> None:
    """AC PA-65 / AD-6: TimeoutStartSec is present and stays inside the
    06:30 MSK deadline (timer fires 05:30, so it must be < 60 min)."""

    values = service_section_values(MORNING, "Service", "TimeoutStartSec")
    assert len(values) == 1
    seconds = parse_seconds(values[0])
    assert 0 < seconds < 60 * 60


def test_morning_timeout_matches_the_documented_value() -> None:
    """The documented carrier value is 55 min (05:30 + 55 < 06:30)."""

    assert service_section_values(MORNING, "Service", "TimeoutStartSec") == ["55min"]


def test_morning_unit_keeps_its_failure_alarm_path() -> None:
    """The deadline is only visible if the overrun raises the same alert."""

    assert service_section_values(MORNING, "Unit", "OnFailure") == ["proxima-alert@%n.service"]


def test_timer_and_unit_stay_inside_the_deadline() -> None:
    """05:30 MSK timer + 55 min timeout < 06:30 MSK deadline (FR-22)."""

    timer = UNITS / "proxima-morning@.timer"
    on_calendar = service_section_values(timer, "Timer", "OnCalendar")
    assert on_calendar == ["*-*-* 05:30:00 Europe/Moscow"]
    timeout = parse_seconds(service_section_values(MORNING, "Service", "TimeoutStartSec")[0])
    assert 5 * 60 + timeout <= 60 * 60
