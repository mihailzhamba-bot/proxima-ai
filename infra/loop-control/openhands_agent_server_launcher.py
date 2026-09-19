#!/usr/bin/python3 -I
"""Load private Agent Server config from fd 0 without exposing it to ACP children."""

from __future__ import annotations

import ctypes
import hmac
import json
import os
import socket
import stat
import sys


PR_SET_DUMPABLE = 4
PR_GET_DUMPABLE = 3
MAX_CONFIG_BYTES = 256 * 1024
RESERVED = {"SESSION_API_KEY", "OH_SECRET_KEY"}


def disable_process_inspection() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0 or libc.prctl(PR_GET_DUMPABLE, 0, 0, 0, 0) != 0:
        raise RuntimeError("cannot disable Agent Server process inspection")


def read_private_config(expected_uid: int = 0) -> bytes:
    info = os.fstat(0)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != expected_uid or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MAX_CONFIG_BYTES:
        raise RuntimeError("private Agent Server config fd is not root-owned mode 0600")
    chunks = []
    total = 0
    while True:
        chunk = os.read(0, min(65536, MAX_CONFIG_BYTES + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_CONFIG_BYTES:
            raise RuntimeError("private Agent Server config exceeds limit")
    null = os.open("/dev/null", os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
    try:
        os.dup2(null, 0)
    finally:
        os.close(null)
    return b"".join(chunks)


def scrub_reserved_environment() -> None:
    for name in tuple(os.environ):
        if name in RESERVED or name.startswith("OH_SESSION_API_KEYS_"):
            os.environ.pop(name, None)


def main() -> None:
    disable_process_inspection()
    raw = read_private_config()
    try:
        payload = json.loads(raw)
        from openhands.agent_server import config as config_module

        config = config_module.Config.model_validate(payload)
    except Exception:
        raise SystemExit("invalid private Agent Server config") from None
    keys=[value for value in config.session_api_keys if isinstance(value,str)]
    secret=config.secret_key.get_secret_value() if config.secret_key is not None else ""
    if len(keys)!=1 or len(keys[0])<32 or keys[0].strip()!=keys[0] or len(secret)<32 or secret.strip()!=secret or hmac.compare_digest(keys[0],secret) or config.max_concurrent_runs!=1:
        raise SystemExit("private Agent Server auth or concurrency config missing")
    config_module._default_config = config
    if config_module.get_default_config() is not config:
        raise SystemExit("private Agent Server config was not cached")
    scrub_reserved_environment()
    with socket.create_connection(("127.0.0.1", 1081), timeout=5):
        pass
    from openhands.agent_server.__main__ import main as agent_server_main

    agent_server_main()


if __name__ == "__main__":
    main()
