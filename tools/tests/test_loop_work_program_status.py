import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import work_program_status as projection
from tools.loop.bridge import Bridge
from tools.loop.native_control import NativeControl
from tools.loop.native_plugin import status_text

NOW = 1_700_000_000
HASH = "b" * 64


def state(**changes):
    return {"status": "idle", "reason": "task_completed", "enabled": True,
            "task_id": "audit-1", "updated_at_utc": projection.stamp(NOW), **changes}


def artifact(**changes):
    return {"artifact_type": "model-research-data-not-admission",
            "task_id": "audit-1", "content_hash": HASH,
            "model": "gpt-5.6-sol", "provider": "openai-codex",
            "created_at_utc": projection.stamp(NOW - 10),
            "actual_provider_route": {"provider": "openai-codex", "model": "gpt-5.6-sol"},
            "verdict": {"summary": "fixture-private-model-text"},
            "context": [{"content": "fixture-private-source"}], **changes}


def projected(**changes):
    event = {"event": "complete", "task_id": "audit-1", "key": "audit-1:" + HASH,
             "artifact": "/fixed/audit-1.json"}
    return projection.build_projection(state(**changes), [event],
                                       lambda *_: artifact(), now=NOW)


def test_only_metadata_is_persisted_and_no_model_text_or_prompt():
    raw = json.dumps(projected())
    assert "fixture-private" not in raw
    assert "verdict" not in raw and "context" not in raw
    parsed = projection.decode_projection(raw, NOW)
    assert parsed["fresh"] is True
    assert parsed["last_result"] == {
        "task_id": "audit-1", "model": "gpt-5.6-sol", "provider": "openai-codex",
        "completed_at_utc": projection.stamp(NOW - 10)}


@pytest.mark.parametrize("age,fresh", [(599, True), (600, False), (601, False)])
def test_freshness_uses_source_and_projection_timestamps(age, fresh):
    raw = json.dumps(projected())
    assert projection.decode_projection(raw, NOW + age)["fresh"] is fresh
    older = projected(updated_at_utc=projection.stamp(NOW - age))
    parsed = projection.decode_projection(json.dumps(older), NOW)
    assert parsed["fresh"] is fresh
    if not fresh:
        assert parsed["status"] == "stale"


@pytest.mark.parametrize("raw", ["{}", "not-json", "x" * 4097,
                                '{"schema_version":1,"schema_version":1}'])
def test_malformed_setting_never_breaks_native_status(raw):
    assert projection.decode_projection(raw, NOW) == {"status": "unavailable", "fresh": False}


@pytest.mark.parametrize("change", [
    {"prompt": "fixture-secret"}, {"status": []}, {"enabled": 1},
    {"projected_at_utc": projection.stamp(NOW + 60)},
    {"source_updated_at_utc": "2026-01-01T12:00:00"},
    {"task_id": "../../secrets"}, {"resume_at": float("nan")},
])
def test_invalid_or_extra_projection_fields_are_not_returned(change):
    value = projected(); value.update(change)
    assert projection.decode_projection(json.dumps(value), NOW)["status"] == "unavailable"


@pytest.mark.parametrize("change", [
    {"provider": "foreign"}, {"model": "unverified-model"},
    {"task_id": "wrong-task"}, {"content_hash": "c" * 64},
    {"actual_provider_route": {"provider": "z.ai", "model": "glm-5.3-flash"}},
])
def test_unbound_artifact_is_not_reported_as_actual_model(change):
    event = {"event": "complete", "task_id": "audit-1", "key": "audit-1:" + HASH}
    value = projection.build_projection(state(), [event], lambda *_: artifact(**change), now=NOW)
    assert value["last_result"] is None


def test_pending_route_is_not_a_confirmed_result_and_artifact_reads_are_bounded():
    events = [{"event": "route", "task_id": "audit-1", "key": "audit-1:" + HASH}]
    assert projection.build_projection(state(status="running"), events,
        lambda *_: pytest.fail("route is not a result"), now=NOW)["last_result"] is None
    calls = []
    def missing(*args):
        calls.append(args)
        raise FileNotFoundError()
    events = [{"event": "complete", "task_id": "audit-1", "key": "audit-1:" + HASH}] * 100
    projection.build_projection(state(), events, missing, now=NOW)
    assert len(calls) <= projection.MAX_ARTIFACT_LOOKUPS


def test_publish_uses_existing_bridge_uid_parameterized_setting_and_no_output():
    calls = []
    projection.publish(projected(), execute=lambda *a, **kw: calls.append((a, kw)))
    argv = calls[0][0][0]; options = calls[0][1]
    assert argv[:7] == ["docker", "exec", "--user", "10001:10001", "-i",
                       "loop-control-bridge-1", "python3"]
    assert options["timeout"] == 10 and options["check"]
    assert options["stderr"] == subprocess.DEVNULL
    assert b"fixture-private" not in options["input"]
    assert "mode=rw" in argv[-1] and "work_program_status" in argv[-1]
    with pytest.raises(ValueError):
        projection.publish({**projected(), "secret": "fixture"}, execute=lambda *_a, **_kw: pytest.fail("bad metadata"))


def test_projector_docker_failure_is_fixed_receipt(monkeypatch, capsys):
    monkeypatch.setattr(projection.os, "geteuid", lambda: 0)
    monkeypatch.setattr(projection.sys, "argv", ["work_program_status.py"])
    monkeypatch.setattr(projection, "read_projection", lambda: projected())
    monkeypatch.setattr(projection, "publish",
                        lambda _: (_ for _ in ()).throw(RuntimeError("fixture-private")))
    assert projection.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "published": False, "reason": "projection_unavailable"}


def test_native_status_keeps_coder_pause_separate_and_review_mode_explicit(tmp_path):
    class Remote:
        def call(self, *_args): return {"status": "idle"}
    bridge = Bridge(tmp_path / "bridge.sqlite", Remote(), Remote(), "director")
    config = {"native_telegram": {"user_id": "12345", "chat_id": "12345", "templates": []}}
    native = NativeControl(bridge, config)
    assert "work_program" not in native.status()
    bridge.pause(True)
    value = projected()
    value["source_updated_at_utc"] = projection.stamp(time.time())
    value["projected_at_utc"] = projection.stamp(time.time())
    with bridge.tx() as db:
        db.execute("INSERT INTO settings VALUES ('work_program_status',?)", (json.dumps(value),))
    result = native.status()
    assert result["queue_paused"] is True
    assert result["work_program"]["status"] == "idle"
    assert result["review_mode"] == "independent_operator_receipt_required"
    text = status_text(result)
    assert "Разработка: на паузе" in text
    assert "Исследования: последнее задание завершено" in text
    assert "OpenAI / gpt-5.6-sol" in text and "МСК" in text
    assert "оператора" in text
    config["native_telegram"]["review_mode"] = "independent_model_receipt_required"
    assert "Ревью: независимая модель" in status_text(native.status())
    config["native_telegram"]["review_mode"] = {}
    assert native.status()["review_mode"] == "unknown"


def test_post_hooks_are_ignored_and_cover_failed_requests():
    unit = (Path(__file__).resolve().parents[2] / "infra/loop-control/loop-work-program.service").read_text()
    for kind in ("ExecStartPost", "ExecStopPost"):
        assert kind + "=-/usr/bin/python3 -I /opt/loop/work_program_status.py" in unit
    assert "Description=LOOP bounded adaptive research" in unit
