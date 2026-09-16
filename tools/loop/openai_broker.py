#!/usr/bin/python3 -I
"""Authenticated loopback broker for the trusted Hermes OpenAI no-tools wrapper."""

from __future__ import annotations

import argparse
import hmac
import json
import math
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

BIND = "127.0.0.1"
PORT = 18772
CONFIG_PATH = Path("/etc/loop/openai-broker.json")
TOKEN_PATH = Path("/etc/loop/secrets/openai_broker")
MAX_CONFIG_BYTES = 16 * 1024
MAX_TOKEN_BYTES = 4 * 1024
MAX_REQUEST_BYTES = 160 * 1024
MAX_PROMPT_BYTES = 128 * 1024
MAX_SYSTEM_BYTES = 32 * 1024
MAX_STDOUT_BYTES = 100 * 1024
MAX_RESPONSE_BYTES = 100 * 1024
READ_TIMEOUT_SECONDS = 10
PROCESS_TIMEOUT_SECONDS = 125
RETRY_AFTER_SECONDS = 15
ALLOWED_MODELS = frozenset({
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-6-astra",
})
ALLOWED_EFFORTS = frozenset({"LOW", "MEDIUM", "HIGH"})
DOCKER_ARGV = [
    "docker", "exec", "--user", "10000:10000", "-i", "loop-control-hermes-1",
    "python3", "/var/lib/loop/hermes/hooks/loop-native/openai_no_tools.py",
]


class BrokerConfigError(RuntimeError):
    pass


class RequestError(ValueError):
    pass


class InferenceError(RuntimeError):
    pass


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def strict_json(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate,
                      parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("invalid number")))


def _secure_chain(path: Path, *, expected_uid: int = 0, anchor: Path = Path("/")) -> None:
    if not path.is_absolute() or not anchor.is_absolute():
        raise BrokerConfigError("untrusted path")
    try:
        relative = path.relative_to(anchor)
    except ValueError:
        raise BrokerConfigError("path outside trust anchor") from None
    current = anchor
    chain = [anchor]
    for part in relative.parts:
        current = current / part
        chain.append(current)
    for item in chain:
        try:
            info = os.lstat(item)
        except OSError:
            raise BrokerConfigError("trusted path unavailable") from None
        if stat.S_ISLNK(info.st_mode):
            raise BrokerConfigError("trusted path contains symlink")
        if info.st_uid != expected_uid:
            raise BrokerConfigError("trusted path has wrong owner")
        if item != path and stat.S_IMODE(info.st_mode) & 0o022:
            raise BrokerConfigError("trusted parent is writable")


def _read_private_file(path: Path, limit: int, *, expected_uid: int = 0,
                       anchor: Path = Path("/")) -> bytes:
    _secure_chain(path, expected_uid=expected_uid, anchor=anchor)
    try:
        info = os.lstat(path)
    except OSError:
        raise BrokerConfigError("private file unavailable") from None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != expected_uid or
            stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > limit):
        raise BrokerConfigError("private file metadata invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise BrokerConfigError("private file changed")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, min(65536, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    raise BrokerConfigError("private file too large")
            return b"".join(chunks)
        finally:
            os.close(fd)
    except BrokerConfigError:
        raise
    except OSError:
        raise BrokerConfigError("private file unavailable") from None


def load_token(config_path: Path = CONFIG_PATH, *, expected_uid: int = 0,
               anchor: Path = Path("/")) -> str:
    if config_path != CONFIG_PATH and anchor == Path("/"):
        raise BrokerConfigError("unexpected config path")
    try:
        config = strict_json(_read_private_file(config_path, MAX_CONFIG_BYTES,
                                                expected_uid=expected_uid, anchor=anchor))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise BrokerConfigError("invalid broker config") from None
    if not isinstance(config, dict) or set(config) != {"token_file"}:
        raise BrokerConfigError("invalid broker config")
    token_path = Path(config["token_file"]) if isinstance(config["token_file"], str) else Path("")
    expected_token = TOKEN_PATH if anchor == Path("/") else anchor / "secrets/openai_broker"
    if token_path != expected_token:
        raise BrokerConfigError("unexpected token path")
    try:
        raw = _read_private_file(token_path, MAX_TOKEN_BYTES, expected_uid=expected_uid, anchor=anchor)
        token = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise BrokerConfigError("invalid broker token") from None
    if token.endswith("\n"):
        token = token[:-1]
    if len(token) < 32 or token.strip() != token or "\n" in token or "\r" in token:
        raise BrokerConfigError("invalid broker token")
    return token


def validate_request(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"prompt", "system", "model", "reasoning_effort"}:
        raise RequestError("invalid_request")
    if any(not isinstance(value[key], str) for key in value):
        raise RequestError("invalid_request")
    prompt = value["prompt"]
    system = value["system"]
    model = value["model"]
    effort = value["reasoning_effort"]
    try:
        prompt_size = len(prompt.encode("utf-8"))
        system_size = len(system.encode("utf-8"))
    except UnicodeEncodeError:
        raise RequestError("invalid_request") from None
    if not prompt or prompt_size > MAX_PROMPT_BYTES:
        raise RequestError("invalid_request")
    if system_size > MAX_SYSTEM_BYTES:
        raise RequestError("invalid_request")
    if model not in ALLOWED_MODELS or effort not in ALLOWED_EFFORTS:
        raise RequestError("invalid_request")
    return {"prompt": prompt, "system": system, "model": model,
            "reasoning_effort": effort.lower()}


def validate_cli_response(value: Any, expected_model: str) -> dict[str, Any]:
    allowed = {"ok", "completed", "response", "model", "provider", "usage"}
    required = {"ok", "response", "model", "provider", "usage"}
    if not isinstance(value, dict) or not required.issubset(value) or not set(value).issubset(allowed):
        raise InferenceError("invalid_output")
    if value["ok"] is not True or ("completed" in value and value["completed"] is not True):
        raise InferenceError("request_failed")
    response = value["response"]
    usage = value["usage"]
    if (not isinstance(response, str) or len(response.encode("utf-8")) > MAX_RESPONSE_BYTES or
            value["model"] != expected_model or value["provider"] != "openai-codex" or
            not isinstance(usage, dict)):
        raise InferenceError("invalid_output")
    for key, amount in usage.items():
        if (not isinstance(key, str) or not key or isinstance(amount, bool) or
                not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0):
            raise InferenceError("invalid_output")
    return {"ok": True, "response": response, "model": expected_model,
            "provider": "openai-codex", "usage": usage}


def _stop_process(process: Any) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=1)
    except Exception:
        try:
            process.kill()
            process.wait(timeout=1)
        except Exception:
            pass


def run_cli(payload: dict[str, str], *, popen_factory: Callable[..., Any] = subprocess.Popen,
            monotonic: Callable[[], float] = time.monotonic,
            sleeper: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with tempfile.TemporaryFile() as stdout_file:
        process = None
        try:
            process = popen_factory(DOCKER_ARGV, stdin=subprocess.PIPE, stdout=stdout_file,
                                    stderr=subprocess.DEVNULL, close_fds=True)
            if process.stdin is None:
                raise InferenceError("launch_failed")
            process.stdin.write(encoded)
            process.stdin.close()
        except Exception:
            if process is not None:
                _stop_process(process)
            raise InferenceError("launch_failed") from None
        deadline = monotonic() + PROCESS_TIMEOUT_SECONDS
        try:
            while True:
                size = os.fstat(stdout_file.fileno()).st_size
                if size > MAX_STDOUT_BYTES:
                    raise InferenceError("output_limit")
                status = process.poll()
                if status is not None:
                    break
                if monotonic() >= deadline:
                    raise InferenceError("timeout")
                sleeper(0.05)
        except InferenceError:
            _stop_process(process)
            raise
        if status != 0:
            raise InferenceError("request_failed")
        if os.fstat(stdout_file.fileno()).st_size > MAX_STDOUT_BYTES:
            raise InferenceError("output_limit")
        stdout_file.seek(0)
        raw = stdout_file.read(MAX_STDOUT_BYTES + 1)
    try:
        value = strict_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise InferenceError("invalid_output") from None
    return validate_cli_response(value, payload["model"])


class BrokerServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address: tuple[str, int], token: str,
                 runner: Callable[[dict[str, str]], dict[str, Any]]) -> None:
        self.token = token
        self.runner = runner
        self.capacity = threading.BoundedSemaphore(1)
        super().__init__(address, BrokerHandler)


class BrokerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "loop-openai-broker"
    sys_version = ""

    @property
    def broker(self) -> BrokerServer:
        return self.server  # type: ignore[return-value]

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(READ_TIMEOUT_SECONDS)

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_error(self, code: int, _message: str | None = None,
                   _explain: str | None = None) -> None:
        status = code if code in {400, 408, 413, 414, 431, 501, 505} else 400
        self._send(status, {"error": "invalid_request"})

    def _send(self, status_code: int, value: dict[str, Any], *, retry_after: bool = False,
              head_only: bool = False) -> None:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        if retry_after:
            self.send_header("Retry-After", str(RETRY_AFTER_SECONDS))
        self.end_headers()
        if not head_only:
            self.wfile.write(raw)
        self.close_connection = True

    def _authorized(self) -> bool:
        values = self.headers.get_all("Authorization", failobj=[])
        expected = "Bearer " + self.broker.token
        if len(values) != 1:
            return False
        try:
            return hmac.compare_digest(values[0], expected)
        except TypeError:
            return False

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send(401, {"error": "unauthorized"})
        return False

    def do_GET(self) -> None:
        if not self._require_auth():
            return
        if self.path != "/health":
            self._send(404, {"error": "not_found"})
            return
        self._send(200, {"ok": True})

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        if self.path != "/v1/infer":
            self._send(404, {"error": "not_found"})
            return
        if not self.broker.capacity.acquire(blocking=False):
            self._send(429, {"error": "busy"}, retry_after=True)
            return
        try:
            self._infer()
        finally:
            self.broker.capacity.release()

    def _infer(self) -> None:
        transfer = self.headers.get_all("Transfer-Encoding", failobj=[])
        lengths = self.headers.get_all("Content-Length", failobj=[])
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if transfer or len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            self._send(400, {"error": "invalid_request"})
            return
        length = int(lengths[0])
        if length <= 0 or length > MAX_REQUEST_BYTES or content_type != "application/json":
            self._send(400 if length <= MAX_REQUEST_BYTES else 413,
                       {"error": "invalid_request" if length <= MAX_REQUEST_BYTES else "request_too_large"})
            return
        try:
            raw = self.rfile.read(length)
        except (TimeoutError, socket.timeout):
            self._send(408, {"error": "request_timeout"})
            return
        if len(raw) != length:
            self._send(400, {"error": "invalid_request"})
            return
        try:
            payload = validate_request(strict_json(raw))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RequestError):
            self._send(400, {"error": "invalid_request"})
            return
        try:
            result = validate_cli_response(self.broker.runner(payload), payload["model"])
        except Exception:
            self._send(502, {"error": "model_unavailable"})
            return
        self._send(200, result)

    def _unsupported(self, *, head_only: bool = False) -> None:
        if not self._require_auth():
            return
        self._send(405, {"error": "method_not_allowed"}, head_only=head_only)

    def do_HEAD(self) -> None:
        self._unsupported(head_only=True)

    do_PUT = _unsupported
    do_PATCH = _unsupported
    do_DELETE = _unsupported
    do_OPTIONS = _unsupported
    do_TRACE = _unsupported
    do_CONNECT = _unsupported


def build_server(token: str, runner: Callable[[dict[str, str]], dict[str, Any]] = run_cli,
                 address: tuple[str, int] = (BIND, PORT)) -> BrokerServer:
    if len(token) < 32 or token.strip() != token:
        raise BrokerConfigError("invalid broker token")
    return BrokerServer(address, token, runner)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    try:
        token = load_token(args.config)
        server = build_server(token)
    except Exception:
        print("openai broker configuration invalid", file=os.sys.stderr)
        return 2
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
