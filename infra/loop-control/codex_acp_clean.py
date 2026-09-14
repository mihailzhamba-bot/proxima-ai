#!/usr/bin/python3 -I
"""Run Codex ACP without server secrets or per-turn sandbox overrides.

``codex-acp`` 1.1.7 always sends a legacy ``sandboxPolicy`` on
``turn/start``.  Codex treats that field as a per-turn override, so it takes
precedence over the named permission profile selected in ``config.toml``.

The outer invocation starts the pinned ACP adapter with this file as
``CODEX_PATH``.  When the adapter starts ``CODEX_PATH app-server``, the inner
invocation proxies the NDJSON app-server protocol and removes only that legacy
override.  Codex then resolves the root-owned ``loop-worker`` profile normally.
Unknown or malformed policy-bearing messages fail closed.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
from collections.abc import Mapping
from queue import SimpleQueue
from typing import BinaryIO

REAL_ACP = "/opt/loop-openhands-agent/node_modules/.bin/codex-acp"
REAL_CODEX = "/opt/loop-openhands-agent/node_modules/.bin/codex"
WRAPPER_PATH = "/opt/loop-openhands-agent/bin/codex-acp"
PERMISSION_PROFILE = "loop-worker"
MAX_MESSAGE_BYTES = 8 * 1024 * 1024
POLICY_METHOD = "turn/start"
THREAD_METHODS = frozenset({"thread/start", "thread/resume"})
EX_CONFIG = 78
WORKSPACE = re.compile(r"^/srv/loop-worker/workspaces/[0-9a-f]{32}$")
ALLOWED = {
    "HOME",
    "CODEX_HOME",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
}


class ProtocolViolation(ValueError):
    """An app-server message cannot be forwarded without weakening policy."""


def permission_contract() -> dict[str, object]:
    """Return the complete session-layer contract; project config cannot override it."""

    return {
        "default_permissions": PERMISSION_PROFILE,
        "approval_policy": "never",
        "permissions": {
            PERMISSION_PROFILE: {
                "description": "LOOP workspace only; host reads and command network are denied.",
                "extends": ":workspace",
                "filesystem": {
                    "glob_scan_max_depth": 8,
                    ":root": "deny",
                    ":minimal": "read",
                    "/opt/loop-openhands-agent/node_modules": "read",
                    ":tmpdir": "deny",
                    ":slash_tmp": "deny",
                    ":workspace_roots": {
                        ".": "write",
                        "proxima-ai/.git": "write",
                        "**/.env": "deny",
                        "**/.env.*": "deny",
                        "**/*secret*": "deny",
                        "**/*token*": "deny",
                    },
                },
                "network": {"enabled": False},
            }
        },
        "shell_environment_policy": {
            "inherit": "none",
            "set": {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/srv/loop-worker/workspaces",
                "USER": "loop-oh-agent",
                "LOGNAME": "loop-oh-agent",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            },
        },
    }


def session_contract(cwd: object) -> dict[str, object]:
    if not isinstance(cwd,str) or not WORKSPACE.fullmatch(cwd):raise ProtocolViolation("thread cwd is outside the dedicated LOOP workspace")
    result=permission_contract()
    result["projects"]={cwd:{"trust_level":"untrusted"},cwd+"/proxima-ai":{"trust_level":"untrusted"}}
    return result


def clean_environment(source: dict[str, str]) -> dict[str, str]:
    result = {name: value for name, value in source.items() if name in ALLOWED}
    result.update(
        PATH="/opt/loop-openhands-agent/node_modules/.bin:/usr/local/bin:/usr/bin:/bin",
        GIT_CONFIG_GLOBAL="/etc/loop-openhands-agent/gitconfig",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
    )
    return result


def acp_environment(source: dict[str, str]) -> dict[str, str]:
    """Return the fixed ACP environment and force the guarded Codex child."""

    result = clean_environment(source)
    result.update(
        CODEX_PATH=WRAPPER_PATH,
        CODEX_CONFIG=json.dumps(permission_contract(), separators=(",", ":")),
        # Safe default for clients which do not explicitly select a mode.  The
        # app-server proxy remains the enforcement point when a client later
        # selects ``agent-full-access``.
        INITIAL_AGENT_MODE="agent",
    )
    return result


def _policy_params(message: Mapping[str, object]) -> dict[str, object]:
    params = message.get("params")
    if not isinstance(params, dict):
        raise ProtocolViolation("policy-bearing request has no object params")
    return params


def rewrite_app_server_message(message: object) -> dict[str, object]:
    """Remove legacy execution overrides from one client-to-Codex request.

    Codex CLI 0.151.0 does not expose ``permissionProfile`` on
    ``turn/start``.  Omitting ``sandboxPolicy`` is its documented way to use
    the configured default, which is the root-owned ``loop-worker`` profile.
    """

    if not isinstance(message, dict):
        raise ProtocolViolation("app-server message is not an object")

    method = message.get("method")
    if method is not None and not isinstance(method, str):
        raise ProtocolViolation("app-server method is not a string")

    rewritten = dict(message)
    if method == POLICY_METHOD:
        params = dict(_policy_params(message))
        params.pop("sandboxPolicy", None)
        if "permissionProfile" in params:
            # The pinned 0.151.0 TurnStartParams schema does not accept this
            # field.  Silently forwarding it would make enforcement depend on
            # undefined version-specific behavior.
            raise ProtocolViolation("unsupported turn permissionProfile")
        rewritten["params"] = params
        return rewritten

    if method in THREAD_METHODS:
        params = dict(_policy_params(message))
        params.pop("sandbox", None)
        if "permissionProfile" in params or "sandboxPolicy" in params:
            raise ProtocolViolation("unsupported thread policy override")
        params["config"]=session_contract(params.get("cwd"))
        rewritten["params"] = params
        return rewritten

    params = message.get("params")
    if isinstance(params, dict) and (
        "sandboxPolicy" in params or "permissionProfile" in params
    ):
        raise ProtocolViolation("policy override on unexpected method")
    return rewritten


def rewrite_app_server_line(line: bytes) -> bytes:
    """Validate and rewrite one newline-terminated app-server JSON message."""

    if not line.endswith(b"\n"):
        raise ProtocolViolation("unterminated app-server message")
    if len(line) > MAX_MESSAGE_BYTES:
        raise ProtocolViolation("app-server message exceeds size limit")
    if not line.strip():
        raise ProtocolViolation("empty app-server message")
    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolViolation("invalid app-server JSON") from exc
    rewritten = rewrite_app_server_message(message)
    return json.dumps(rewritten, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    ) + b"\n"


def _forward_client_requests(
    source: BinaryIO,
    destination: BinaryIO,
    child: subprocess.Popen[bytes],
    errors: SimpleQueue[BaseException],
) -> None:
    try:
        while line := source.readline(MAX_MESSAGE_BYTES + 1):
            destination.write(rewrite_app_server_line(line))
            destination.flush()
    except BrokenPipeError:
        return
    except (OSError, ProtocolViolation) as exc:
        errors.put(exc)
        child.terminate()
    finally:
        try:
            destination.close()
        except BrokenPipeError:
            pass


def _install_signal_forwarders(
    child: subprocess.Popen[bytes],
) -> dict[int, signal.Handlers]:
    previous: dict[int, signal.Handlers] = {}

    def forward(signum: int, _frame: object) -> None:
        if child.poll() is None:
            child.send_signal(signum)

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, forward)
    return previous


def _restore_signal_handlers(previous: Mapping[int, signal.Handlers]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def run_app_server_proxy(
    source: BinaryIO | None = None,
    destination: BinaryIO | None = None,
) -> int:
    """Run the real app server behind the fail-closed NDJSON policy proxy."""

    source = source or sys.stdin.buffer
    destination = destination or sys.stdout.buffer
    child = subprocess.Popen(
        [REAL_CODEX, "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        env=clean_environment(dict(os.environ)),
        bufsize=0,
    )
    if child.stdin is None or child.stdout is None:  # pragma: no cover - Popen contract
        child.terminate()
        return EX_CONFIG

    errors: SimpleQueue[BaseException] = SimpleQueue()
    writer = threading.Thread(
        target=_forward_client_requests,
        args=(source, child.stdin, child, errors),
        name="codex-app-server-policy-writer",
        daemon=True,
    )
    previous = _install_signal_forwarders(child)
    writer.start()
    try:
        while chunk := child.stdout.read(64 * 1024):
            destination.write(chunk)
            destination.flush()
        returncode = child.wait()
    finally:
        _restore_signal_handlers(previous)

    if not errors.empty():
        # Never include the rejected payload: it can contain prompts or tool
        # output.  The fixed message is sufficient for operators and alerts.
        print(
            "codex ACP policy proxy rejected an unsafe app-server message",
            file=sys.stderr,
            flush=True,
        )
        return EX_CONFIG
    return returncode


def main() -> None:
    args = sys.argv[1:]
    if args == ["app-server"]:
        raise SystemExit(run_app_server_proxy())
    if args and args[0] == "app-server":
        print("unsupported codex app-server arguments", file=sys.stderr, flush=True)
        raise SystemExit(EX_CONFIG)
    os.execve(REAL_ACP, [REAL_ACP, *args], acp_environment(dict(os.environ)))


if __name__ == "__main__":
    main()
