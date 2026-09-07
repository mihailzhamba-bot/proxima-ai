"""Offline tests for tools/proxima_alert.sh (PA-65).

No network. curl is replaced by a recording stub on PATH (the pattern the
shellcheck/verify CI job and other wrapper tests use): the stub captures the
curl --config lines and exits with the configured status, so we can assert
what the script would send and how curl would be told to retry.
"""

from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "proxima_alert.sh"

# Placeholder secret values for the sandbox, not real credentials: the
# 35-character body of a genuine Telegram token matches the secret-scan
# pattern, so both values deliberately miss it.
FAKE_TOKEN = "000000000:AAAA" + "0" * 30
FAKE_CHAT_ID = "000000000"


class StubCurl:
    """Recording stand-in for the curl binary.

    The script invokes curl exactly once per run; curl's own `--retry`
    re-drives the transfer inside that single process, so a stub can only
    ever observe one invocation. It records the fed `--config` lines and
    exits with the configured curl-style status code.
    """

    def __init__(self, directory: Path, status: int) -> None:
        self.calls = 0
        script = textwrap.dedent(
            f"""
            #!/usr/bin/env bash
            set -euo pipefail
            call_file="$CURL_CALL_FILE"
            count_file="$CURL_CALL_FILE.count"
            runs=0
            [[ -e "$count_file" ]] && runs="$(cat "$count_file")"
            runs=$((runs + 1))
            printf '%s' "$runs" > "$count_file"
            cat >> "$call_file"
            printf '\\n--- call %s ---\\n' "$runs" >> "$call_file"
            exit "{status}"
            """
        ).lstrip("\n")
        stub = directory / "curl"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.stub = stub


@pytest.fixture()
def alert_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the secret files into the sandbox and expose a stub curl."""

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "telegram_bot_token").write_text(FAKE_TOKEN + "\n", encoding="utf-8")
    (secrets / "telegram_chat_id").write_text(FAKE_CHAT_ID + "\n", encoding="utf-8")
    monkeypatch.setenv("PROXIMA_ALERT_SECRETS_DIR", str(secrets))
    return secrets


def run_alert(unit: str = "proxima-morning@test.service", **env: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.update({key: value for key, value in env.items() if value is not None})
    return subprocess.run(
        ["bash", str(SCRIPT), unit],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
        check=False,
    )


def curl_config_lines(call_file: Path) -> list[str]:
    return [line.strip() for line in call_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_retry_config_lines_reach_curl(alert_sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC PA-65 / D25 solution 4a / AD-6: the Telegram send carries
    `retry = 3` and `retry-delay = 5` in the curl --config payload."""

    call_file = tmp_path / "curl-calls.log"
    monkeypatch.setenv("CURL_CALL_FILE", str(call_file))
    stub = StubCurl(tmp_path, status=0)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    result = run_alert()
    assert result.returncode == 0, result.stderr

    lines = curl_config_lines(call_file)
    assert "retry = 3" in lines
    assert "retry-delay = 5" in lines
    assert any(line.startswith("url = ") and "api.telegram.org" in line for line in lines)
    expected_payload = [
        f'url = "https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage"',
        f'data-urlencode = "chat_id={FAKE_CHAT_ID}"',
        'data-urlencode = "text=PROXIMA AI unit failed: proxima-morning@test.service"',
        "fail",
        "silent",
        "show-error",
        "max-time = 20",
        "retry = 3",
        "retry-delay = 5",
    ]
    assert lines == expected_payload + ["--- call 1 ---"]


def test_5xx_failure_would_be_retried_by_curl(alert_sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC PA-65: the send is not one-shot — the config carries the retry
    budget (3 retries, 5 s apart), which makes curl re-drive HTTP 5xx,
    408, 429 and transport-level failures inside its single invocation.
    A synthetic failure code passes straight through to the script."""

    call_file = tmp_path / "curl-calls.log"
    monkeypatch.setenv("CURL_CALL_FILE", str(call_file))
    stub = StubCurl(tmp_path, status=18)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    result = run_alert()
    assert result.returncode == 18, result.stderr
    assert "retry = 3" in curl_config_lines(call_file)
    assert "retry-delay = 5" in curl_config_lines(call_file)


def test_4xx_is_not_retried(alert_sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC PA-65: the script's contribution to 4xx fail-fast is that it does
    NOT enable retry-all-errors (without it curl retries only 408/429/5xx
    and transport errors). A 4xx-shaped exit 22 surfaces unchanged."""

    call_file = tmp_path / "curl-calls.log"
    monkeypatch.setenv("CURL_CALL_FILE", str(call_file))
    stub = StubCurl(tmp_path, status=22)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    result = run_alert()
    assert result.returncode == 22
    assert all("retry-all-errors" not in line for line in curl_config_lines(call_file))


def test_transport_timeout_budget_reaches_curl(alert_sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC PA-65: `max-time = 20` caps each attempt and pairs with the retry
    budget, so a hanging Telegram endpoint keeps the send inside the
    morning unit's `TimeoutStartSec=55min` deadline. A timeout-shaped exit
    28 passes through unchanged."""

    call_file = tmp_path / "curl-calls.log"
    monkeypatch.setenv("CURL_CALL_FILE", str(call_file))
    stub = StubCurl(tmp_path, status=28)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    result = run_alert()
    assert result.returncode == 28, result.stderr
    assert "max-time = 20" in curl_config_lines(call_file)
    assert "retry = 3" in curl_config_lines(call_file)


def test_missing_secrets_keeps_failing_before_any_curl_run(alert_sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Behavior for an unreadable secret file is unchanged: no curl run,
    non-zero exit, message on stderr."""

    (alert_sandbox / "telegram_bot_token").unlink()
    call_file = tmp_path / "curl-calls.log"
    monkeypatch.setenv("CURL_CALL_FILE", str(call_file))
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    result = run_alert()
    assert result.returncode != 0
    assert "secret files are unavailable" in result.stderr
    assert not call_file.exists()


def test_empty_secret_file_keeps_failing_before_any_curl_run(alert_sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty secret file fails before any curl run, as before PA-65."""

    (alert_sandbox / "telegram_chat_id").write_text("\n", encoding="utf-8")
    call_file = tmp_path / "curl-calls.log"
    monkeypatch.setenv("CURL_CALL_FILE", str(call_file))
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    result = run_alert()
    assert result.returncode != 0
    assert "empty Telegram secret file" in result.stderr
    assert not call_file.exists()


def test_script_text_keeps_the_runbook_grep_expectation() -> None:
    """The release runbook greps for `retry` in the script and expects
    `--retry 3 --retry-delay 5` wording to be verifiable on the server."""

    text = SCRIPT.read_text(encoding="utf-8")
    assert "--retry 3 --retry-delay 5" in text
    assert "retry = 3" in text
    assert "retry-delay = 5" in text
