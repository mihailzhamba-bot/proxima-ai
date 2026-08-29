from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ENV = (
    "PROXIMA_TENANT_ID",
    "PROXIMA_DATABASE_URL_FILE",
    "PROXIMA_SIGNAL_RAW_DIR",
    "WB_STATISTICS_TOKEN_FILE",
    "WB_ANALYTICS_TOKEN_FILE",
    "WB_FINANCE_TOKEN_FILE",
)


def clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (*REQUIRED_ENV, "PROXIMA_ALLOW_ANALYTICS_READ_WRITE"):
        environment.pop(name, None)
    return environment


def configured_environment(tmp_path: Path) -> tuple[dict[str, str], str]:
    environment = clean_environment()
    secret_value = "must-not-appear-in-command-output"
    database_url = tmp_path / "postgres_url"
    statistics_token = tmp_path / "wb_statistics_token"
    analytics_token = tmp_path / "wb_analytics_token"
    finance_token = tmp_path / "wb_finance_token"
    for path in (database_url, statistics_token, analytics_token, finance_token):
        path.write_text(f"{secret_value}\n", encoding="utf-8")
        path.chmod(0o600)
    environment.update(
        {
            "PROXIMA_TENANT_ID": "test-tenant",
            "PROXIMA_DATABASE_URL_FILE": str(database_url),
            "PROXIMA_SIGNAL_RAW_DIR": str(tmp_path / "raw"),
            "WB_STATISTICS_TOKEN_FILE": str(statistics_token),
            "WB_ANALYTICS_TOKEN_FILE": str(analytics_token),
            "WB_FINANCE_TOKEN_FILE": str(finance_token),
        }
    )
    return environment, secret_value


def fake_runner(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "runner.log"
    runner = tmp_path / "runner"
    runner.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$PROXIMA_TEST_RUNNER_LOG\"\n",
        encoding="utf-8",
    )
    runner.chmod(0o700)
    return runner, log


def run_make(target: str, environment: dict[str, str], *variables: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "--no-print-directory", target, *variables],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_runtime_preflight_names_missing_variable_without_leaking_values(tmp_path: Path) -> None:
    environment, secret_value = configured_environment(tmp_path)
    environment.pop("PROXIMA_TENANT_ID")

    result = run_make("dev", environment)

    assert result.returncode != 0
    assert "PROXIMA_TENANT_ID is required" in result.stderr
    assert secret_value not in result.stdout + result.stderr


def test_runtime_preflight_names_unreadable_file_without_printing_its_path(tmp_path: Path) -> None:
    environment, secret_value = configured_environment(tmp_path)
    missing_path = tmp_path / "private-path-must-not-appear"
    environment["WB_STATISTICS_TOKEN_FILE"] = str(missing_path)
    runner, _ = fake_runner(tmp_path)

    result = run_make("dev", environment, f"TSX={runner}")

    assert result.returncode != 0
    assert "WB_STATISTICS_TOKEN_FILE must point to a readable regular file" in result.stderr
    assert str(missing_path) not in result.stdout + result.stderr
    assert secret_value not in result.stdout + result.stderr


def test_start_builds_and_runs_compiled_dry_run(tmp_path: Path) -> None:
    environment, secret_value = configured_environment(tmp_path)
    runner, log = fake_runner(tmp_path)
    environment["PROXIMA_TEST_RUNNER_LOG"] = str(log)

    result = run_make("start", environment, f"NPM={runner}", f"TSX={runner}")

    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls[0] == "run build"
    assert calls[1].startswith("--silent --workspace @proxima/collector run stockout-signal -- --tenant test-tenant ")
    assert "--database-url-file" in calls[1]
    assert "--raw-root" in calls[1]
    assert "--send" not in calls[1]
    assert "--allow-analytics-read-write" not in calls[1]
    assert secret_value not in result.stdout + result.stderr


def test_dev_runs_typescript_with_explicit_analytics_exception(tmp_path: Path) -> None:
    environment, secret_value = configured_environment(tmp_path)
    runner, log = fake_runner(tmp_path)
    environment["PROXIMA_TEST_RUNNER_LOG"] = str(log)
    environment["PROXIMA_ALLOW_ANALYTICS_READ_WRITE"] = "1"

    result = run_make("dev", environment, f"TSX={runner}")

    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 1
    assert calls[0].startswith("services/collector/src/cli/stockout-signal.ts --tenant test-tenant ")
    assert calls[0].endswith("--allow-analytics-read-write")
    assert "--send" not in calls[0]
    assert secret_value not in result.stdout + result.stderr


def test_runtime_preflight_rejects_unknown_analytics_exception_value(tmp_path: Path) -> None:
    environment, _ = configured_environment(tmp_path)
    environment["PROXIMA_ALLOW_ANALYTICS_READ_WRITE"] = "yes"
    runner, _ = fake_runner(tmp_path)

    result = run_make("dev", environment, f"TSX={runner}")

    assert result.returncode != 0
    assert "PROXIMA_ALLOW_ANALYTICS_READ_WRITE must be 0 or 1" in result.stderr
