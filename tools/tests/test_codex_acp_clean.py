import importlib.util
import io
import json
import os
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "infra/loop-control/codex_acp_clean.py"
SPEC = importlib.util.spec_from_file_location("codex_acp_clean", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
codex_acp_clean = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = codex_acp_clean
SPEC.loader.exec_module(codex_acp_clean)


def encoded(message: object) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode() + b"\n"


def test_wrapper_pins_installed_sibling_binaries() -> None:
    assert (
        codex_acp_clean.REAL_ACP
        == "/opt/loop-openhands-agent/node_modules/.bin/codex-acp"
    )
    assert (
        codex_acp_clean.REAL_CODEX
        == "/opt/loop-openhands-agent/node_modules/.bin/codex"
    )


@pytest.mark.parametrize(
    "sandbox_policy",
    [
        {"type": "dangerFullAccess"},
        {
            "type": "workspaceWrite",
            "writableRoots": ["/"],
            "networkAccess": True,
        },
    ],
)
def test_turn_start_removes_every_legacy_sandbox_override(
    sandbox_policy: dict[str, object],
) -> None:
    message = {
        "id": 7,
        "method": "turn/start",
        "params": {
            "threadId": "thread-1",
            "input": [{"type": "text", "text": "fixture"}],
            "approvalPolicy": "never",
            "sandboxPolicy": sandbox_policy,
        },
    }

    rewritten = json.loads(codex_acp_clean.rewrite_app_server_line(encoded(message)))

    assert "sandboxPolicy" not in rewritten["params"]
    assert rewritten["params"]["threadId"] == "thread-1"
    assert rewritten["params"]["approvalPolicy"] == "never"
    assert rewritten["params"]["input"] == message["params"]["input"]


def test_turn_start_without_override_still_uses_configured_default() -> None:
    message = {
        "id": 8,
        "method": "turn/start",
        "params": {"threadId": "thread-2", "input": []},
    }

    result = json.loads(codex_acp_clean.rewrite_app_server_line(encoded(message)))
    assert result["params"] == {**message["params"], "model": "gpt-5.6-sol", "effort": "medium", "serviceTier": None}


def test_turn_cannot_override_approved_model_or_reasoning_budget() -> None:
    result = codex_acp_clean.rewrite_app_server_message({
        "method": "turn/start", "params": {
            "model": "expensive-unapproved", "effort": "xhigh", "serviceTier": "fast",
            "collaborationMode": {"mode": "default", "settings": {
                "model": "expensive-unapproved", "reasoning_effort": "xhigh",
                "developer_instructions": None,
            }},
        },
    })["params"]
    assert (result["model"], result["effort"], result["serviceTier"]) == ("gpt-5.6-sol", "medium", None)
    assert result["collaborationMode"]["settings"] == {
        "model": "gpt-5.6-sol", "reasoning_effort": "medium", "developer_instructions": None,
    }


@pytest.mark.parametrize(
    "line",
    [
        b'{"method":"turn/start"',
        b'{"method":"turn/start","params":{}}',
        b"[]\n",
        b"\n",
    ],
)
def test_malformed_or_unterminated_transport_fails_closed(line: bytes) -> None:
    with pytest.raises(codex_acp_clean.ProtocolViolation):
        codex_acp_clean.rewrite_app_server_line(line)


def test_unexpected_policy_override_fails_closed() -> None:
    message = {
        "id": 9,
        "method": "command/exec",
        "params": {
            "command": ["true"],
            "permissionProfile": "unrestricted",
        },
    }

    with pytest.raises(codex_acp_clean.ProtocolViolation):
        codex_acp_clean.rewrite_app_server_line(encoded(message))


def test_thread_start_drops_legacy_sandbox_before_profile_resolution() -> None:
    cwd="/srv/loop-worker/workspaces/"+"a"*32
    message = {
        "id": 10,
        "method": "thread/start",
        "params": {"cwd": cwd, "sandbox": "danger-full-access","config":{"permissions":{"loop-worker":{"filesystem":{"/":"write"},"network":{"enabled":True}}},"projects":{cwd:{"trust_level":"trusted"}}}},
    }

    rewritten = json.loads(codex_acp_clean.rewrite_app_server_line(encoded(message)))

    assert "sandbox" not in rewritten["params"]
    assert rewritten["params"]["config"]==codex_acp_clean.session_contract(cwd)
    assert rewritten["params"]["config"]["projects"][cwd]["trust_level"]=="untrusted"
    assert rewritten["params"]["config"]["permissions"]["loop-worker"]["network"]["enabled"] is False


def test_acp_environment_scrubs_secrets_and_forces_guarded_codex_child() -> None:
    environment = codex_acp_clean.acp_environment(
        {
            "HOME": "/srv/loop-worker/codex-home",
            "CODEX_HOME": "/srv/loop-worker/codex-home",
            "SESSION_API_KEY": "must-not-pass",
            "CODEX_PATH": "/tmp/bypass",
            "CODEX_CONFIG": '{"default_permissions":"unrestricted"}',
            "INITIAL_AGENT_MODE": "agent-full-access",
            "PATH": "/tmp/bypass",
            "TMPDIR": "/srv/loop-worker/agent-state/tmp",
        }
    )

    assert environment["CODEX_PATH"] == codex_acp_clean.WRAPPER_PATH
    assert json.loads(environment["CODEX_CONFIG"]) == codex_acp_clean.permission_contract()
    assert environment["INITIAL_AGENT_MODE"] == "agent"
    assert environment["TMPDIR"] == "/srv/loop-worker/agent-state/tmp"
    assert environment["PATH"].startswith(
        "/opt/loop-openhands-agent/node_modules/.bin:"
    )
    assert "SESSION_API_KEY" not in environment
    assert "CODEX_CONFIG" not in codex_acp_clean.clean_environment(environment)


def test_session_permission_contract_matches_root_owned_toml() -> None:
    configured=tomllib.loads((ROOT/"infra/loop-control/codex-worker.config.toml").read_text())
    assert codex_acp_clean.permission_contract()==configured


def test_thread_outside_dedicated_workspace_fails_closed() -> None:
    with pytest.raises(codex_acp_clean.ProtocolViolation,match="outside"):
        codex_acp_clean.rewrite_app_server_message({"method":"thread/resume","params":{"cwd":"/srv/proxima-ai","config":{}}})


def test_outer_wrapper_execs_pinned_acp_with_guarded_environment(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execve(path: str, argv: list[str], environment: dict[str, str]) -> None:
        captured.update(path=path, argv=argv, environment=environment)
        raise RuntimeError("execve intercepted")

    monkeypatch.setattr(sys, "argv", ["codex-acp", "--fixture"])
    monkeypatch.setattr(os, "execve", fake_execve)
    monkeypatch.setenv("SESSION_API_KEY", "must-not-pass")

    with pytest.raises(RuntimeError, match="execve intercepted"):
        codex_acp_clean.main()

    assert captured["path"] == codex_acp_clean.REAL_ACP
    assert captured["argv"] == [codex_acp_clean.REAL_ACP, "--fixture"]
    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["CODEX_PATH"] == codex_acp_clean.WRAPPER_PATH
    assert "SESSION_API_KEY" not in environment


def test_app_server_proxy_removes_override_before_child_ipc(
    tmp_path: Path, monkeypatch
) -> None:
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        "#!/usr/bin/python3\n"
        "import sys\n"
        "assert sys.argv[1:] == ['app-server']\n"
        "for line in sys.stdin.buffer:\n"
        "    sys.stdout.buffer.write(line)\n"
        "    sys.stdout.buffer.flush()\n"
    )
    fake_codex.chmod(0o755)
    monkeypatch.setattr(codex_acp_clean, "REAL_CODEX", str(fake_codex))
    request = {
        "id": 11,
        "method": "turn/start",
        "params": {
            "threadId": "thread-3",
            "input": [],
            "sandboxPolicy": {"type": "dangerFullAccess"},
        },
    }
    child_output = io.BytesIO()

    returncode = codex_acp_clean.run_app_server_proxy(
        source=io.BytesIO(encoded(request)), destination=child_output
    )

    assert returncode == 0
    forwarded = json.loads(child_output.getvalue())
    assert forwarded["method"] == "turn/start"
    assert "sandboxPolicy" not in forwarded["params"]


def test_app_server_proxy_stops_child_on_invalid_transport(
    tmp_path: Path, monkeypatch
) -> None:
    fake_codex = tmp_path / "waiting-codex"
    fake_codex.write_text(
        "#!/usr/bin/python3\n"
        "import sys\n"
        "assert sys.argv[1:] == ['app-server']\n"
        "for line in sys.stdin.buffer:\n"
        "    sys.stdout.buffer.write(line)\n"
        "    sys.stdout.buffer.flush()\n"
    )
    fake_codex.chmod(0o755)
    monkeypatch.setattr(codex_acp_clean, "REAL_CODEX", str(fake_codex))

    returncode = codex_acp_clean.run_app_server_proxy(
        source=io.BytesIO(b'{"method":"turn/start"'), destination=io.BytesIO()
    )

    assert returncode == codex_acp_clean.EX_CONFIG


def test_unknown_app_server_arguments_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["codex-acp", "app-server", "--unknown"])

    with pytest.raises(SystemExit) as exc_info:
        codex_acp_clean.main()

    assert exc_info.value.code == codex_acp_clean.EX_CONFIG
