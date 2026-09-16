import http.client
import io
import json
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import openai_broker as broker

TOKEN = "t" * 32


def request(server, method, path, body=None, token=TOKEN, headers=None):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    request_headers = {"Authorization": "Bearer " + token}
    if data is not None:
        request_headers.update({"Content-Type": "application/json", "Content-Length": str(len(data))})
    request_headers.update(headers or {})
    connection = http.client.HTTPConnection(*server.server_address, timeout=2)
    connection.request(method, path, body=data, headers=request_headers)
    response = connection.getresponse()
    raw = response.read()
    result = response.status, dict(response.getheaders()), (json.loads(raw) if raw else None)
    connection.close()
    return result


@pytest.fixture
def running_server():
    calls = []
    def runner(payload):
        calls.append(payload)
        return {"ok": True, "response": "answer", "model": payload["model"],
                "provider": "openai-codex", "usage": {"total_tokens": 3}}
    server = broker.build_server(TOKEN, runner, ("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, calls
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def valid_request(**changes):
    value = {"prompt": "Do the bounded task.", "system": "No tools.",
             "model": "gpt-5.6-sol", "reasoning_effort": "MEDIUM"}
    value.update(changes)
    return value


def test_authenticated_health_and_inference(running_server):
    server, calls = running_server
    assert request(server, "GET", "/health") == (200, request(server, "GET", "/health")[1], {"ok": True})
    status, _headers, value = request(server, "POST", "/v1/infer", valid_request())
    assert status == 200 and value["provider"] == "openai-codex"
    assert calls == [{**valid_request(), "reasoning_effort": "medium"}]


def test_non_ascii_authorization_fails_closed(running_server):
    server, calls = running_server
    status, _headers, value = request(server, "GET", "/health", token="é" * 32)
    assert status == 401 and value == {"error": "unauthorized"} and calls == []


def test_auth_required_and_never_calls_model(running_server):
    server, calls = running_server
    assert request(server, "GET", "/health", token="wrong")[0:3:2] == (401, {"error": "unauthorized"})
    assert request(server, "POST", "/v1/infer", valid_request(), token="wrong")[0] == 401
    assert calls == []


@pytest.mark.parametrize("change", [
    {"model": "gpt-6-astra-ultra"}, {"reasoning_effort": "high"},
    {"reasoning_effort": "ULTRA"}, {"prompt": ""}, {"extra": "field"},
])
def test_strict_request_schema_rejects_before_runner(running_server, change):
    server, calls = running_server
    status, _headers, value = request(server, "POST", "/v1/infer", valid_request(**change))
    assert status == 400 and value == {"error": "invalid_request"}
    assert calls == []


def test_duplicate_json_keys_chunked_invalid_length_and_methods(running_server):
    server, calls = running_server
    duplicate = b'{"prompt":"a","prompt":"b","system":"","model":"gpt-5.5","reasoning_effort":"LOW"}'
    assert request(server, "POST", "/v1/infer", duplicate)[0] == 400

    conn = http.client.HTTPConnection(*server.server_address, timeout=2)
    conn.putrequest("POST", "/v1/infer")
    conn.putheader("Authorization", "Bearer " + TOKEN)
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Transfer-Encoding", "chunked")
    conn.endheaders(); conn.send(b"0\r\n\r\n")
    assert conn.getresponse().status == 400
    conn.close()

    conn = http.client.HTTPConnection(*server.server_address, timeout=2)
    conn.putrequest("POST", "/v1/infer")
    conn.putheader("Authorization", "Bearer " + TOKEN)
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", "abc")
    conn.endheaders()
    assert conn.getresponse().status == 400
    conn.close()
    assert request(server, "PUT", "/v1/infer")[0] == 405
    assert calls == []


def test_capacity_one_returns_retry_after_without_second_call():
    entered = threading.Event(); release = threading.Event(); calls = []
    def runner(payload):
        calls.append(payload); entered.set(); release.wait(timeout=2)
        return {"ok": True, "response": "done", "model": payload["model"],
                "provider": "openai-codex", "usage": {}}
    server = broker.build_server(TOKEN, runner, ("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    first = threading.Thread(target=lambda: request(server, "POST", "/v1/infer", valid_request()))
    first.start(); assert entered.wait(timeout=1)
    status, headers, value = request(server, "POST", "/v1/infer", valid_request())
    assert status == 429 and headers["Retry-After"] == "15" and value == {"error": "busy"}
    assert len(calls) == 1
    release.set(); first.join(timeout=2); server.shutdown(); server.server_close(); thread.join(timeout=2)


class FakeProcess:
    def __init__(self, argv, *, stdin, stdout, stderr, close_fds, output=b"", status=0, polls=0):
        self.argv = argv; self.stdout = stdout; self.stderr = stderr
        position = stdin.tell(); stdin.seek(0); self.stdin_data = stdin.read(); stdin.seek(position)
        self.status = status; self.polls = polls
        self.terminated = False; self.killed = False
        stdout.write(output); stdout.flush()
        assert stdin != broker.subprocess.PIPE and stderr == broker.subprocess.DEVNULL and close_fds is True

    def poll(self):
        if self.polls:
            self.polls -= 1
            return None
        return self.status

    def terminate(self): self.terminated = True
    def kill(self): self.killed = True
    def wait(self, timeout): return self.status


class Clock:
    def __init__(self): self.value = 0
    def __call__(self): return self.value


class SlowInput(io.BytesIO):
    def __init__(self, clock): super().__init__(); self.clock = clock
    def write(self, value):
        self.clock.value += broker.PROCESS_TIMEOUT_SECONDS * 8
        return super().write(value)


def cli_output(model="gpt-5.6-sol"):
    return json.dumps({"ok": True, "completed": True, "response": "answer",
        "model": model, "provider": "openai-codex", "usage": {"total_tokens": 2}}).encode()


def test_fake_subprocess_uses_fixed_argv_stdin_and_normalizes_output():
    made = []
    def factory(*args, **kwargs):
        process = FakeProcess(*args, **kwargs, output=cli_output()); made.append(process); return process
    result = broker.run_cli({**valid_request(), "reasoning_effort": "medium"}, popen_factory=factory)
    assert made[0].argv == broker.DOCKER_ARGV
    assert json.loads(made[0].stdin_data)["prompt"] == "Do the bounded task."
    assert set(result) == {"ok", "response", "model", "provider", "usage"}


def test_stdin_tempfile_write_is_inside_absolute_deadline_and_never_spawns():
    clock = Clock(); made = []
    def factory(*args, **kwargs):
        made.append((args, kwargs))
        raise AssertionError("process must not spawn after expired input setup")
    with pytest.raises(broker.InferenceError, match="timeout"):
        broker.run_cli({**valid_request(), "reasoning_effort": "medium"},
                       popen_factory=factory, monotonic=clock,
                       stdin_factory=lambda: SlowInput(clock))
    assert made == []


def test_fake_subprocess_killed_on_stdout_limit():
    made = []
    def factory(*args, **kwargs):
        process = FakeProcess(*args, **kwargs, output=b"x" * (broker.MAX_STDOUT_BYTES + 1), polls=1)
        made.append(process); return process
    with pytest.raises(broker.InferenceError, match="output_limit"):
        broker.run_cli({**valid_request(), "reasoning_effort": "medium"}, popen_factory=factory)
    assert made[0].terminated


def test_fake_subprocess_killed_on_absolute_timeout():
    made = []; clock = Clock()
    def factory(*args, **kwargs):
        process = FakeProcess(*args, **kwargs, polls=5); made.append(process); return process
    def advance(_seconds): clock.value = broker.PROCESS_TIMEOUT_SECONDS + 1
    with pytest.raises(broker.InferenceError, match="timeout"):
        broker.run_cli({**valid_request(), "reasoning_effort": "medium"}, popen_factory=factory,
                       monotonic=clock, sleeper=advance)
    assert made[0].terminated


@pytest.mark.parametrize("change", [
    {"provider": "other"}, {"model": "gpt-5.5"}, {"usage": {"x": True}},
    {"usage": {"x": -1}}, {"completed": False}, {"secret": "leak"},
])
def test_cli_response_fails_closed(change):
    value = json.loads(cli_output())
    value.update(change)
    with pytest.raises(broker.InferenceError):
        broker.validate_cli_response(value, "gpt-5.6-sol")


def test_private_config_and_token_require_0600_nonsymlink_chain(tmp_path):
    anchor = tmp_path / "trusted"; anchor.mkdir(mode=0o700)
    secrets = anchor / "secrets"; secrets.mkdir(mode=0o700)
    token = secrets / "openai_broker"; token.write_text(TOKEN + "\n"); token.chmod(0o600)
    config = anchor / "openai-broker.json"
    config.write_text(json.dumps({"token_file": str(token)})); config.chmod(0o600)
    assert broker.load_token(config, anchor=anchor) == TOKEN
    token.chmod(0o644)
    with pytest.raises(broker.BrokerConfigError):
        broker.load_token(config, anchor=anchor)


def test_systemd_unit_is_root_bounded_and_read_only():
    unit = (Path(__file__).resolve().parents[2] / "infra/loop-control/loop-openai-broker.service").read_text()
    for expected in ["User=root", "NoNewPrivileges=yes", "PrivateTmp=yes", "ProtectHome=yes",
                     "ProtectSystem=strict", "MemoryMax=256M", "CPUQuota=50%", "TasksMax=32",
                     "Restart=on-failure", "IPAddressAllow=localhost",
                     "ReadOnlyPaths=/etc/loop/openai-broker.json /etc/loop/secrets/openai_broker /var/run/docker.sock"]:
        assert expected in unit
