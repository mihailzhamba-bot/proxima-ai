"""Owner confirmation is a native Telegram event, never model-generated text."""
import asyncio
import hashlib
import json
import sys
import threading
import time
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop.bridge import Bridge, BridgeError, JsonHTTP, server, template_fingerprint
from tools.loop.native_control import NativeControl
from tools.loop.native_plugin import NativePlugin, PENDING, authorized, register

TEMPLATE = {"profile": "fedor", "profile_id": "11111111-1111-4111-8111-111111111111",
            "profile_revision": 0, "base_sha": "a" * 40, "allowed_paths": ["probe.ts"]}
ACTOR = {"user_id": "12345", "chat_id": "12345", "chat_type": "dm"}


class Remote:
    def __init__(self):
        self.calls = []
        self.offline = False
    def call(self, method, path, payload=None, headers=None):
        self.calls.append((method, path, payload))
        if method == "POST" and self.offline:
            raise BridgeError(502, "lost response", True)
        if path.endswith("wakeup"):
            return {"id": "paperclip-run"}
        if path == "/v1/runs":
            return {"id": "hermes-run"}
        return {"status": "idle"}


def setup(tmp_path):
    remote = Remote()
    bridge = Bridge(tmp_path / "bridge.sqlite", remote, remote, "director")
    config = {"native_telegram": {**ACTOR, "templates": ["probe"], "descriptions": {"probe": {
        "description": "Add the fixed test marker", "expected_result": "One-file PR"}}}, "templates": {"probe": dict(TEMPLATE)}}
    native = NativeControl(bridge, config)
    return bridge, native, config, remote


def prepare(native):
    draft = native.draft({"template": "probe"})
    payload = {**ACTOR, "draft_id": draft["draft_id"]}
    preview = native.preview(payload)
    native.preview_receipt({**payload, "preview_nonce": preview["preview_nonce"], "message_id": "42"})
    return payload


def test_discussion_draft_preview_do_not_dispatch_and_require_owner(tmp_path):
    bridge, native, _, remote = setup(tmp_path)
    draft = native.draft({"template": "probe"})
    payload = {**ACTOR, "draft_id": draft["draft_id"]}
    with pytest.raises(BridgeError, match="loop_review"):
        native.confirm(payload)
    for update in [{"user_id": "9"}, {"chat_id": "9"}, {"chat_type": "group"}]:
        with pytest.raises(BridgeError, match="owner"):
            native.preview({**payload, **update})
    native.preview(payload)
    assert remote.calls == []
    with bridge.tx() as db:
        assert db.execute("SELECT count(*) FROM operations").fetchone()[0] == 0


def test_confirmation_durable_duplicate_and_exact_template_binding(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    payload = prepare(native)
    first = native.confirm(payload)
    restored = NativeControl(bridge, config)
    assert restored.confirm(payload)["run_id"] == first["run_id"]
    assert len([c for c in remote.calls if c[1].endswith("wakeup")]) == 1
    child = bridge.create("hermes", "paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    job = {"job_id": "tg-" + payload["draft_id"].replace("-", ""), "run_id": child["run_id"], "generation": 1, "template": "probe"}
    with pytest.raises(BridgeError, match="owner-confirmed"):
        bridge.propose_job({**job, "job_id": "another-job"}, config["templates"])
    assert bridge.propose_job(job, config["templates"])["state"] == "queued"


def test_unknown_parent_cannot_propose_before_wakeup_ack(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    with pytest.raises(BridgeError, match="parent binding"):
        bridge.create("hermes", "unacknowledged-parent", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    assert not any(c[1] == "/v1/runs" for c in remote.calls)


def test_undelivered_or_superseded_preview_cannot_authorize(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    draft = native.draft({"template": "probe"})
    payload = {**ACTOR, "draft_id": draft["draft_id"]}
    first = native.preview(payload)
    with pytest.raises(BridgeError, match="loop_review"):
        native.confirm(payload)
    native.preview(payload)
    with pytest.raises(BridgeError, match="superseded"):
        native.preview_receipt({**payload, "preview_nonce": first["preview_nonce"], "message_id": "42"})
    assert remote.calls == []


@pytest.mark.parametrize("change", ["pause", "expire", "template"])
def test_pause_expiry_and_changed_template_never_launch(tmp_path, change):
    bridge, native, config, remote = setup(tmp_path)
    payload = prepare(native)
    if change == "pause":
        bridge.pause(True)
    elif change == "expire":
        with bridge.tx() as db:
            db.execute("UPDATE native_drafts SET created=?", (time.time() - 1000,))
    else:
        config["templates"]["probe"]["base_sha"] = "b" * 40
    with pytest.raises(BridgeError):
        native.confirm(payload)
    assert not any(c[0] == "POST" for c in remote.calls)


def test_unknown_dispatch_and_restart_never_retry_upstream(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    payload = prepare(native)
    remote.offline = True
    with pytest.raises(BridgeError):
        native.confirm(payload)
    assert NativeControl(bridge, config).confirm(payload)["status"] == "unknown"
    assert len([c for c in remote.calls if c[0] == "POST"]) == 1


def test_crash_before_intent_requires_reconciliation(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    payload = prepare(native)
    with bridge.tx() as db:
        db.execute("UPDATE native_drafts SET state='dispatching'")
    with pytest.raises(BridgeError, match="unknown"):
        NativeControl(bridge, config).confirm(payload)
    assert remote.calls == []


def test_http_model_credential_cannot_confirm_stop_or_wake(tmp_path):
    bridge, native, config, _ = setup(tmp_path)
    keys = {}
    for role in ["operator", "director", "gateway", "runner", "chat", "native_ingress"]:
        p = tmp_path / role
        p.write_text(role + "-secret")
        p.chmod(0o600)
        keys[role] = str(p)
    http = server(bridge, {**config, "port": 0, "credential_files": keys})
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        client = JsonHTTP("http://127.0.0.1:" + str(http.server_port), "chat-secret", trusted_bridge=True)
        assert "queue_paused" in client.call("GET", "/v1/chat/status")
        for path in ["/v1/native/confirm", "/v1/native/stop", "/v1/wake", "/v1/jobs", "/v1/native-recovery/retry"]:
            with pytest.raises(BridgeError) as exc:
                client.call("POST", path, ACTOR)
            assert exc.value.status == 403
    finally:
        http.shutdown()
        http.server_close()


def event(text="hello", **changes):
    source = SimpleNamespace(platform="telegram", chat_type="dm", user_id="12345", chat_id="12345", is_bot=False)
    evt = SimpleNamespace(source=source, text=text, allow_gateway_control=True, internal=False)
    for key, val in changes.items():
        setattr(source if hasattr(source, key) else evt, key, val)
    return evt


@pytest.mark.parametrize("changes", [{"user_id": "9"}, {"chat_id": "9"}, {"chat_type": "group"},
                                    {"is_bot": True}, {"internal": True}, {"allow_gateway_control": False}])
def test_native_event_provenance_fails_closed(changes):
    plugin = NativePlugin(ACTOR)
    evt = event("/loop_confirm fake", **changes)
    assert not authorized(evt, ACTOR)
    assert plugin.gate(evt, None)["action"] == "skip"


def test_native_chat_passes_through_but_slash_controls_never_reach_model():
    async def exercise():
        plugin = NativePlugin(ACTOR)
        seen = []
        async def handle(gateway, source, command, args, actor):
            seen.append((command, args, actor))
        plugin.handle = handle
        assert plugin.gate(event("Discuss the goal"), None) is None
        for command in ["/loop_confirm abc", "/tools", "/cron", "/model", "/plugins", "/unknown"]:
            assert plugin.gate(event(command), None)["action"] == "skip"
        if PENDING:
            await asyncio.gather(*list(PENDING))
        assert seen[0] == ("loop_confirm", "abc", ACTOR)
    asyncio.run(exercise())


def test_cached_voice_transcript_cannot_become_owner_confirmation():
    plugin = NativePlugin(ACTOR)
    voice = event('')
    voice.message_type = 'voice'
    voice._gateway_pending_stt_text = '/loop_confirm 11111111-1111-4111-8111-111111111111'
    before = set(PENDING)
    assert plugin.gate(voice, None) is None
    assert PENDING == before


def test_notification_claim_does_not_resend_after_restart(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    native.confirm(prepare(native))
    item = native.notifications()["pending"][0]
    native.notification_action(item["id"], "claim", {})
    restored = NativeControl(bridge, config)
    assert restored.notifications()["pending"] == []
    assert restored.notifications()["delivery_unknown"] == 1


@pytest.mark.parametrize("success", [True, False, "exception"])
def test_native_preview_requires_successful_telegram_delivery_receipt(tmp_path, success):
    bridge, native, config, remote = setup(tmp_path)
    draft = native.draft({"template": "probe"})
    payload = {**ACTOR, "draft_id": draft["draft_id"]}
    class Client:
        def call(self, method, path, body=None):
            return native.route(method, path, body or {})
    class Adapter:
        async def send(self, chat_id, text):
            if success == "exception":
                raise OSError("fixture transport failure")
            return SimpleNamespace(success=success, message_id="42" if success else None)
    plugin = NativePlugin(ACTOR)
    plugin.client = lambda role: Client()
    gateway = SimpleNamespace(_adapter_for_source=lambda source: Adapter())
    asyncio.run(plugin.handle(gateway, event().source, "loop_review", draft["draft_id"], ACTOR))
    if success is True:
        assert native.confirm(payload)["run_id"]
    else:
        with pytest.raises(BridgeError, match="loop_review"):
            native.confirm(payload)
        assert remote.calls == []


def test_changed_human_description_invalidates_approval(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    payload = prepare(native)
    config["native_telegram"]["descriptions"]["probe"]["description"] = "A different edit"
    with pytest.raises(BridgeError, match="template changed"):
        native.confirm(payload)
    assert remote.calls == []


def test_plugin_registration_requires_no_running_event_loop(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(ACTOR))
    monkeypatch.setenv('LOOP_NATIVE_CONFIG', str(path))
    seen = {"hooks": [], "tools": [], "commands": []}
    ctx = SimpleNamespace(
        register_hook=lambda *a, **kw: seen['hooks'].append(a),
        register_tool=lambda **kw: seen['tools'].append(kw),
        register_command=lambda *a, **kw: seen['commands'].append(a))
    register(ctx)
    assert seen['hooks'][0][0] == 'pre_gateway_dispatch'
    assert {t['name'] for t in seen['tools']} == {'loop_get_status', 'loop_prepare_action'}
    assert len(seen['commands']) == 4
    monkeypatch.setattr(NativePlugin, 'model_call', lambda self, name, args: json.dumps({'name': name}))
    for tool in seen['tools']:
        assert json.loads(tool['handler']({}, task_id='native-fixture'))['name'] == tool['name']


def test_hermes_only_restart_exposes_uncertain_delivery_without_resending(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    native.confirm(prepare(native))
    item = native.notifications()['pending'][0]
    native.notification_action(item['id'], 'claim', {})
    assert native.status()['notification_deliveries']['sending'] == 1
    # Bridge remains alive; only the notifier disappeared after claim.
    with bridge.tx() as db:
        db.execute('UPDATE native_notifications SET claimed_at=?', (time.time() - 121,))
    assert native.notifications()['pending'] == []
    assert native.status()['notification_deliveries']['delivery_unknown'] == 1
    with pytest.raises(BridgeError, match='already claimed'):
        native.notification_action(item['id'], 'claim', {})


def test_script_entrypoint_preserves_native_error_identity(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    key = tmp_path / 'key'
    key.write_text('fixture-private-key')
    key.chmod(0o600)
    config = {
        'port': port, 'database': str(tmp_path / 'script.sqlite'), 'director_id': 'fixture',
        'credential_files': {role: str(key) for role in ['chat', 'native_ingress', 'operator', 'gateway', 'runner', 'director']},
        'hermes': {'url': 'http://127.0.0.1:1', 'token_file': str(key)},
        'paperclip': {'url': 'http://127.0.0.1:1', 'token_file': str(key)},
        'native_telegram': {**ACTOR, 'templates': []}}
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parents[1] / 'loop/bridge.py'), '--config', str(path)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        client = JsonHTTP('http://127.0.0.1:' + str(port), 'fixture-private-key', timeout=2, trusted_bridge=True)
        for _ in range(80):
            try:
                status = client.call('GET', '/v1/chat/status')
                break
            except BridgeError:
                if process.poll() is not None:
                    pytest.fail('Bridge script exited')
                time.sleep(.025)
        else:
            pytest.fail('Bridge script did not return native status')
        assert status['director_status'] == 'unknown'
        with pytest.raises(BridgeError) as exc:
            client.call('POST', '/v1/native/confirm', {**ACTOR, 'user_id': '9'})
        assert exc.value.status == 403
        assert exc.value.uncertain is False
    finally:
        process.terminate()
        process.wait(timeout=5)


def completed_attempt(tmp_path):
    bridge, native, config, remote = setup(tmp_path)
    payload = prepare(native)
    parent = native.confirm(payload)
    child = bridge.create("hermes", "paperclip-run", {"input": "spoofed task", "instructions": "Read WB first", "session_id": "fixture"})
    with bridge.tx() as db:
        db.execute("UPDATE operations SET state='completed'")
    original_call = remote.call
    def call(method, path, body=None, headers=None):
        if method == "GET" and (path.startswith("/api/heartbeat-runs/") or path.startswith("/v1/runs/")):
            remote.calls.append((method, path, body))
            return {"status": "completed"}
        if path.endswith("wakeup"):
            result = original_call(method, path, body, headers)
            return {"id": "retry-paperclip-run"}
        return original_call(method, path, body, headers)
    remote.call = call
    return bridge, native, config, remote, payload, parent, child


def test_captured_native_input_is_persisted_envelope(tmp_path):
    bridge, native, _, remote, payload, _, child = completed_attempt(tmp_path)
    body = next(c[2] for c in remote.calls if c[1] == "/v1/runs")
    envelope = json.loads(body["input"].split("native task: ", 1)[1])
    assert envelope == native.approved_execution(native.get_draft(payload["draft_id"]))
    assert child["run_id"] in body["input"]
    assert "spoofed task" not in body["input"]
    assert "Read WB first" not in body["instructions"]


@pytest.mark.parametrize("change", ["fingerprint", "job_id", "approval", "missing"])
def test_spoofed_parent_envelope_never_executes(tmp_path, change):
    bridge, native, _, remote = setup(tmp_path)
    payload = prepare(native)
    parent = native.confirm(payload)
    with bridge.tx() as db:
        request = json.loads(db.execute("SELECT request FROM operations WHERE id=?", (parent["run_id"],)).fetchone()[0])
        if change == "missing":
            request = {}
        else:
            request[{"fingerprint": "template_fingerprint", "job_id": "job_id", "approval": "approval_fingerprint"}[change]] = "spoof"
        db.execute("UPDATE operations SET request=? WHERE id=?", (json.dumps(request), parent["run_id"]))
    with pytest.raises(BridgeError, match="owner-approved|envelope missing"):
        bridge.create("hermes", "paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    assert not any(c[1] == "/v1/runs" for c in remote.calls)


def test_completed_no_job_retry_is_durable_and_follows_pointer(tmp_path):
    bridge, native, _, remote, payload, parent, child = completed_attempt(tmp_path)
    retry = {"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]}
    result = native.retry(retry)
    assert result["run_id"] != parent["run_id"]
    assert native.retry(retry)["run_id"] == result["run_id"]
    assert native.confirm(payload)["run_id"] == result["run_id"]
    assert len([c for c in remote.calls if c[1].endswith("wakeup")]) == 2
    assert bridge.get(parent["run_id"])["state"] == "completed"
    native.notifications()
    with bridge.tx() as db:
        texts = [r[0] for r in db.execute("SELECT text FROM native_notifications")]
    assert any(result["run_id"] in t for t in texts)
    native.stop({**ACTOR, "run_id": parent["run_id"]})
    assert bridge.get(result["run_id"])["state"] == "cancelling"
    with pytest.raises(BridgeError, match="approval"):
        native.retry(retry)
    with pytest.raises(BridgeError, match="approval"):
        bridge.create("hermes", "retry-paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})


def test_retry_lost_response_never_dispatches_twice(tmp_path):
    bridge, native, config, remote, payload, parent, _ = completed_attempt(tmp_path)
    retry = {"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]}
    remote.offline = True
    with pytest.raises(BridgeError):
        native.retry(retry)
    with pytest.raises(BridgeError) as exc:
        NativeControl(bridge, config).retry(retry)
    assert exc.value.uncertain
    assert len([c for c in remote.calls if c[1].endswith("wakeup")]) == 2


@pytest.mark.parametrize("blocker", ["job", "cancelled", "unknown", "fresh_running", "changed"])
def test_retry_rejects_unsafe_attempts(tmp_path, blocker):
    bridge, native, config, remote, payload, parent, child = completed_attempt(tmp_path)
    if blocker == "job":
        with bridge.tx() as db:
            db.execute("INSERT INTO jobs(id,director_run,generation,template) VALUES(?,?,1,'probe')", ("other-job", child["run_id"]))
    elif blocker in {"cancelled", "unknown"}:
        with bridge.tx() as db:
            db.execute("UPDATE operations SET state=? WHERE id=?", (blocker, parent["run_id"]))
    elif blocker == "changed":
        config["templates"]["probe"]["base_sha"] = "b" * 40
    else:
        original = remote.call
        remote.call = lambda method, path, body=None, headers=None: {"status": "running"} if method == "GET" else original(method, path, body, headers)
    with pytest.raises(BridgeError):
        native.retry({"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]})
    assert len([c for c in remote.calls if c[1].endswith("wakeup")]) == 1


def test_parent_ack_wait_does_not_hold_database_lock(tmp_path):
    bridge, native, _, remote = setup(tmp_path)
    payload = prepare(native)
    parent = native.confirm(payload)
    with bridge.tx() as db:
        db.execute("UPDATE operations SET external_id=NULL WHERE id=?", (parent["run_id"],))
    def acknowledge():
        time.sleep(.05)
        with bridge.tx() as db:
            db.execute("UPDATE operations SET external_id='paperclip-run' WHERE id=?", (parent["run_id"],))
    thread = threading.Thread(target=acknowledge)
    thread.start()
    result = bridge.create("hermes", "paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result["status"] == "running"


def test_missing_owner_approval_never_executes(tmp_path):
    bridge, native, _, remote = setup(tmp_path)
    payload = prepare(native)
    native.confirm(payload)
    with bridge.tx() as db:
        db.execute("UPDATE native_drafts SET preview_message=NULL")
    with pytest.raises(BridgeError, match="approval"):
        bridge.create("hermes", "paperclip-run", {"input": "owner approved", "instructions": "fixture", "session_id": "fixture"})
    assert not any(c[1] == "/v1/runs" for c in remote.calls)


def test_cancel_old_parent_revokes_current_retry_child_and_proposals(tmp_path):
    bridge, native, config, remote, payload, parent, _ = completed_attempt(tmp_path)
    retry = native.retry({"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]})
    child = bridge.create("hermes", "retry-paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    native.stop({**ACTOR, "run_id": parent["run_id"]})
    assert bridge.get(child["run_id"])["state"] == "cancelled"
    assert bridge.get(retry["run_id"])["state"] == "cancelled"
    with pytest.raises(BridgeError):
        bridge.propose_job({"job_id": "tg-" + payload["draft_id"].replace("-", ""), "run_id": child["run_id"], "generation": 1, "template": "probe"}, config["templates"])


def test_cancel_fences_retry_intent_with_lost_ack(tmp_path):
    bridge, native, _, remote, payload, parent, _ = completed_attempt(tmp_path)
    remote.offline = True
    with pytest.raises(BridgeError):
        native.retry({"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]})
    with bridge.tx() as db:
        intent = db.execute("SELECT id FROM operations WHERE key=?", ("native-retry-" + parent["run_id"],)).fetchone()[0]
    native.stop({**ACTOR, "run_id": parent["run_id"]})
    assert bridge.get(intent)["state"] == "cancelling"
    assert native.get_draft(payload["draft_id"])["state"] == "cancelled"


def test_retry_supersedes_pending_old_notifications_but_keeps_journal(tmp_path):
    bridge, native, _, _, payload, parent, _ = completed_attempt(tmp_path)
    old = native.notifications()["pending"][0]["id"]
    retry = native.retry({"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]})
    pending = native.notifications()["pending"]
    assert old not in {item["id"] for item in pending}
    with bridge.tx() as db:
        assert db.execute("SELECT state FROM native_notifications WHERE id=?", (old,)).fetchone()[0] == "superseded"


def test_cancel_entire_retry_chain_before_old_parent_network_call(tmp_path):
    bridge, native, config, remote, payload, parent, _ = completed_attempt(tmp_path)
    retry = native.retry({"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]})
    child = bridge.create("hermes", "retry-paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    job_id = "tg-" + payload["draft_id"].replace("-", "")
    bridge.propose_job({"job_id": job_id, "run_id": child["run_id"], "generation": 1, "template": "probe"}, config["templates"])
    original = remote.call
    observed = []
    def call(method, path, body=None, headers=None):
        if method == "POST" and path.endswith("/cancel"):
            observed.append(bridge.get(child["run_id"])["state"])
            assert bridge.job(job_id)["state"] == "cancelled"
            with pytest.raises(BridgeError) as exc:
                bridge.fence(job_id)
            assert exc.value.revoked
        return original(method, path, body, headers)
    remote.call = call
    native.stop({**ACTOR, "run_id": parent["run_id"]})
    assert observed and observed[0] == "cancelling"


def test_cancel_persists_barrier_before_waiting_native_lock(tmp_path):
    bridge, native, _, _, payload, parent, _ = completed_attempt(tmp_path)
    execution = native.approved_execution(native.get_draft(payload["draft_id"]))
    errors = []
    def stop():
        try:
            native.stop({**ACTOR, "run_id": parent["run_id"]})
        except BaseException as exc:
            errors.append(exc)
    with native.lock:
        thread = threading.Thread(target=stop)
        thread.start()
        deadline = time.monotonic() + 2
        while native.get_draft(payload["draft_id"])["state"] != "cancelled" and time.monotonic() < deadline:
            time.sleep(.01)
        assert native.get_draft(payload["draft_id"])["state"] == "cancelled"
        assert thread.is_alive()
        with pytest.raises(BridgeError, match="approval"):
            bridge.create("paperclip", "native-retry-" + parent["run_id"], execution)
    thread.join(timeout=2)
    assert not thread.is_alive() and not errors


def test_operator_batch_envelope_uses_persisted_exact_contract(tmp_path):
    bridge, _, config, remote = setup(tmp_path)
    payload = {"source": "operator_batch", "job_id": "night-probe-001", "template": "probe",
               "template_fingerprint": template_fingerprint("probe", config["templates"]["probe"]), "goal": "Spoof arbitrary WB work"}
    parent = bridge.create("paperclip", "night20260915-probe", payload)
    child = bridge.create("hermes", "paperclip-run", {"input": "fake approval", "instructions": "Read WB", "session_id": "fixture"})
    captured = next(c[2] for c in remote.calls if c[1] == "/v1/runs")
    envelope = json.loads(captured["input"].split("batch task: ", 1)[1])
    assert envelope == json.loads(bridge.get(parent["run_id"])["request"])
    assert "approval_fingerprint" not in envelope and "draft_id" not in envelope
    assert "fake approval" not in captured["input"] and "Spoof arbitrary" not in captured["input"]
    job = {"job_id": payload["job_id"], "template": "probe", "run_id": child["run_id"], "generation": 1}
    with pytest.raises(BridgeError):
        bridge.propose_job({**job, "job_id": "another-job"}, config["templates"])
    assert bridge.propose_job(job, config["templates"])["state"] == "queued"


@pytest.mark.parametrize("change", ["fingerprint", "template", "fake_approval", "missing", "job"])
def test_operator_batch_rejects_invalid_contract_before_dispatch(tmp_path, change):
    bridge, _, config, remote = setup(tmp_path)
    payload = {"source": "operator_batch", "job_id": "night-probe-001", "template": "probe",
               "template_fingerprint": template_fingerprint("probe", config["templates"]["probe"])}
    if change == "missing":
        del payload["template_fingerprint"]
    else:
        key = {"fingerprint": "template_fingerprint", "template": "template", "fake_approval": "approval_fingerprint", "job": "job_id"}[change]
        payload[key] = "FAKE"
    with pytest.raises(BridgeError):
        bridge.create("paperclip", "night20260915-probe", payload)
    assert not remote.calls


def test_operator_batch_template_change_or_parent_cancel_fences_execution(tmp_path):
    bridge, _, config, remote = setup(tmp_path)
    payload = {"source": "operator_batch", "job_id": "night-probe-001", "template": "probe",
               "template_fingerprint": template_fingerprint("probe", config["templates"]["probe"])}
    parent = bridge.create("paperclip", "night20260915-probe", payload)
    config["templates"]["probe"]["base_sha"] = "b" * 40
    with pytest.raises(BridgeError, match="fingerprint"):
        bridge.create("hermes", "paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    config["templates"]["probe"]["base_sha"] = "a" * 40
    bridge.cancel(parent["run_id"])
    with pytest.raises(BridgeError):
        bridge.create("hermes", "paperclip-run", {"input": "fixture", "instructions": "fixture", "session_id": "fixture"})
    assert not any(c[1] == "/v1/runs" for c in remote.calls)


def test_operator_http_wakeup_preserves_batch_contract_and_credentials(tmp_path):
    bridge, _, config, remote = setup(tmp_path)
    keys = {}
    for role in ["operator", "director", "gateway", "runner", "chat", "native_ingress"]:
        key = tmp_path / role
        key.write_text(role + "-secret")
        key.chmod(0o600)
        keys[role] = str(key)
    http = server(bridge, {**config, "port": 0, "credential_files": keys})
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(http.server_port)
    body = {"source": "operator_batch", "job_id": "night-probe-001", "template": "probe",
            "template_fingerprint": template_fingerprint("probe", config["templates"]["probe"])}
    try:
        for role in ["chat", "native_ingress", "director"]:
            with pytest.raises(BridgeError) as exc:
                JsonHTTP(base, role + "-secret").call("POST", "/v1/wake", body, {"Idempotency-Key": "night20260915-probe"})
            assert exc.value.status == 403
        result = JsonHTTP(base, "operator-secret").call("POST", "/v1/wake", body, {"Idempotency-Key": "night20260915-probe"})
        assert result["status"] == "running"
        JsonHTTP(base, "gateway-secret").call("POST", "/hermes/v1/runs", {"input": "fixture", "instructions": "WB first", "session_id": "fixture"}, {"Idempotency-Key": "paperclip-run", "X-Hermes-Session-Key": "fixture"})
        captured = next(c[2] for c in remote.calls if c[1] == "/v1/runs")
        assert "operator-authorized batch task" in captured["input"]
        assert body["job_id"] in captured["input"]
    finally:
        http.shutdown()
        http.server_close()


@pytest.mark.parametrize("delivery", ["delivered", "delivery_unknown", "sending", "pending"])
def test_legacy_notification_receipt_migration_never_creates_resend(tmp_path, delivery):
    bridge, native, config, _, payload, parent, _ = completed_attempt(tmp_path)
    legacy_id = hashlib.sha256(json.dumps([payload["draft_id"], None, "completed", None]).encode()).hexdigest()
    with bridge.tx() as db:
        db.execute("ALTER TABLE native_notifications DROP COLUMN run_id")
        db.execute("INSERT INTO native_notifications(id,text,state,created) VALUES(?,?,?,?)",
                   (legacy_id, "LOOP: completed.\nЗапуск: " + parent["run_id"], delivery, time.time()))
    restored = NativeControl(bridge, config)
    pending = restored.notifications()["pending"]
    assert [item["id"] for item in pending] == ([legacy_id] if delivery == "pending" else [])
    with bridge.tx() as db:
        receipts = db.execute("SELECT id,state,run_id FROM native_notifications").fetchall()
    assert len(receipts) == 1
    assert receipts[0]["state"] == ("delivery_unknown" if delivery == "sending" else delivery)
    assert receipts[0]["run_id"] == parent["run_id"]


@pytest.mark.parametrize("delivery", ["delivered", "delivery_unknown"])
def test_legacy_receipt_does_not_suppress_same_event_on_new_retry(tmp_path, delivery):
    bridge, native, config, _, payload, parent, _ = completed_attempt(tmp_path)
    legacy_id = hashlib.sha256(json.dumps([payload["draft_id"], None, "completed", None]).encode()).hexdigest()
    with bridge.tx() as db:
        db.execute("ALTER TABLE native_notifications DROP COLUMN run_id")
        db.execute("INSERT INTO native_notifications(id,text,state,created) VALUES(?,?,?,?)",
                   (legacy_id, "LOOP: completed.\nЗапуск: " + parent["run_id"], delivery, time.time()))
    restored = NativeControl(bridge, config)
    assert restored.notifications()["pending"] == []
    retry = restored.retry({"draft_id": payload["draft_id"], "failed_run_id": parent["run_id"]})
    with bridge.tx() as db:
        db.execute("UPDATE operations SET state='completed' WHERE id=?", (retry["run_id"],))
    pending = restored.notifications()["pending"]
    assert len(pending) == 1 and pending[0]["id"] != legacy_id
    with bridge.tx() as db:
        assert db.execute("SELECT state FROM native_notifications WHERE id=?", (legacy_id,)).fetchone()[0] == delivery
        assert db.execute("SELECT run_id FROM native_notifications WHERE id=?", (pending[0]["id"],)).fetchone()[0] == retry["run_id"]
