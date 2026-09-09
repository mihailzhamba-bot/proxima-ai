"""Static and dry-run contract tests for the disposable CI-parity harness."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "ci_parity.sh"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), "--dry-run", *args], capture_output=True, text=True, timeout=30)


def test_bash_syntax() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True).returncode == 0


def test_default_dry_run_is_isolated_and_uses_default_port() -> None:
    result = run()
    assert result.returncode == 0, result.stderr
    assert "docker compose -p proxima-ciparity" in result.stdout
    assert "PROXIMA_CI_PARITY_PORT=5436" in result.stdout
    assert "down -v --remove-orphans" in result.stdout
    for forbidden in ("proxima-ai-postgres-1", "/srv/proxima-ai", "/etc/proxima-ai/secrets"):
        assert forbidden not in result.stdout


@pytest.mark.parametrize(("only", "present", "absent"), [
    ("db", "npm --workspace @proxima/collector run test:db", "systemd-analyze verify"),
    ("migrations", "control-plane-admin make apply-migrations", "test:db"),
    ("systemd", "systemd-analyze verify", "docker compose"),
])
def test_only_filters_checks(only: str, present: str, absent: str) -> None:
    result = run("--only", only)
    assert result.returncode == 0, result.stderr
    assert present in result.stdout
    assert absent not in result.stdout


def test_port_override_and_dsn_exports() -> None:
    result = run("--only", "db", "--port", "6543")
    assert result.returncode == 0, result.stderr
    assert "PROXIMA_CI_PARITY_PORT=6543" in result.stdout
    for name in (
        "PROXIMA_TEST_DSN_COLLECTOR", "PROXIMA_TEST_DSN_NORM", "PROXIMA_TEST_DSN_WEBAPP",
        "PROXIMA_TEST_DSN_JANITOR", "PROXIMA_TEST_DSN_SANDBOX", "PROXIMA_TEST_POSTGRES_DSN",
    ):
        assert name in result.stdout


def test_cleanup_trap_is_declared() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "trap cleanup EXIT INT TERM" in text
    assert "compose down -v --remove-orphans" in text
