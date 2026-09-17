from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "loop/wb_daily_status.py"
NOW = datetime(2026, 9, 17, 6, 0, tzinfo=timezone.utc)


def load_module():
    spec = importlib.util.spec_from_file_location("wb_daily_status", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(**changes):
    value = {
        "tenant": "amirova-test",
        "scope": "isolated rehearsal",
        "state": "success",
        "started_at": "2026-09-17T04:00:00+00:00",
        "finished_at": "2026-09-17T04:05:00+00:00",
        "verified": {
            "last_full_day": "2026-09-16",
            "stale": False,
            "collected_at": "2026-09-17T04:02:00+00:00",
            "brief_day": "2026-09-16",
            "brief_status": "ok",
            "actual": {"orders": 1},
            "norm": {"sample_days": 14, "window_days": 14},
        },
    }
    value.update(changes)
    return value


def assert_shape(result):
    assert list(result) == [
        "tenant_id", "state", "analyzed_day", "collected_at",
        "last_attempt_at", "reason_code",
    ]


def test_complete_current_snapshot_is_success_and_bounded():
    result = load_module().project_daily_status(snapshot(), NOW)
    assert result == {
        "tenant_id": "amirova-test",
        "state": "success",
        "analyzed_day": "2026-09-16",
        "collected_at": "2026-09-17T04:02:00+00:00",
        "last_attempt_at": "2026-09-17T04:05:00+00:00",
        "reason_code": None,
    }


def test_midnight_uses_yesterday_in_moscow_not_utc():
    midnight = datetime(2026, 9, 16, 21, 30, tzinfo=timezone.utc)
    value = snapshot(
        started_at="2026-09-16T21:05:00Z",
        finished_at="2026-09-16T21:10:00Z",
    )
    value["verified"].update(
        last_full_day="2026-09-16",
        brief_day="2026-09-16",
        collected_at="2026-09-16T21:08:00Z",
    )
    assert load_module().project_daily_status(value, midnight)["state"] == "success"


@pytest.mark.parametrize("mutation,reason", [
    (lambda value: value["verified"].__setitem__("stale", True), "data_stale"),
    (lambda value: value["verified"].__setitem__("stale", 0), "data_stale"),
    (lambda value: value["verified"].__setitem__("brief_day", "2026-09-15"), "day_mismatch"),
    (lambda value: value["verified"].__setitem__("brief_status", "blocked"), "brief_not_ready"),
    (lambda value: value["verified"]["norm"].__setitem__("sample_days", 13), "norm_incomplete"),
    (lambda value: value["verified"]["norm"].__setitem__("window_days", True), "norm_incomplete"),
    (lambda value: value["verified"].pop("actual"), "snapshot_incomplete"),
    (lambda value: value["verified"].pop("brief_day"), "snapshot_incomplete"),
    (lambda value: value["verified"].__setitem__("last_full_day", "credential=do-not-expose"), "snapshot_incomplete"),
])
def test_incomplete_or_unverified_data_is_unavailable(mutation, reason):
    value = snapshot()
    mutation(value)
    result = load_module().project_daily_status(value, NOW)
    assert result["state"] == "unavailable"
    assert result["reason_code"] == reason
    assert_shape(result)


@pytest.mark.parametrize("field,bad", [
    ("started_at", "not-a-time"),
    ("started_at", "2026-09-17T07:00:00Z"),
    ("finished_at", "2026-09-17T07:00:00Z"),
])
def test_malformed_and_future_run_timestamps_are_rejected(field, bad):
    value = snapshot(**{field: bad})
    assert load_module().project_daily_status(value, NOW)["state"] == "unavailable"


def test_future_collected_timestamp_is_rejected():
    value = snapshot()
    value["verified"]["collected_at"] = "2026-09-17T07:00:00Z"
    result = load_module().project_daily_status(value, NOW)
    assert result["reason_code"] == "timestamp_invalid"


def test_old_success_cannot_claim_readiness():
    value = snapshot(
        started_at="2026-09-16T05:00:00Z",
        finished_at="2026-09-16T05:05:00Z",
    )
    value["verified"]["collected_at"] = "2026-09-16T05:02:00Z"
    result = load_module().project_daily_status(value, NOW)
    assert result["state"] == "unavailable"
    assert result["reason_code"] == "snapshot_old"


def test_running_and_failure_use_fixed_reasons_and_ignore_raw_error():
    module = load_module()
    running = snapshot(state="running")
    failed = snapshot(state="failed", error="credential=do-not-expose")
    assert module.project_daily_status(running, NOW) == {
        "tenant_id": "amirova-test",
        "state": "running",
        "analyzed_day": None,
        "collected_at": None,
        "last_attempt_at": "2026-09-17T04:00:00+00:00",
        "reason_code": "collector_running",
    }
    result = module.project_daily_status(failed, NOW)
    assert result["state"] == "failed"
    assert result["reason_code"] == "collector_failed"
    assert "credential" not in json.dumps(result)


def test_secret_and_arbitrary_field_injection_is_not_projected():
    value = snapshot(
        password="do-not-expose",
        error="do-not-expose",
        reason_code="attacker-controlled",
        arbitrary={"nested": "do-not-expose"},
    )
    value["verified"]["access_token"] = "do-not-expose"
    result = load_module().project_daily_status(value, NOW)
    assert_shape(result)
    assert "do-not-expose" not in json.dumps(result)
    assert result["reason_code"] is None


def test_read_adapter_handles_missing_invalid_and_oversize_files(tmp_path):
    module = load_module()
    missing = module.read_daily_status(tmp_path / "missing.json", NOW)
    assert missing["state"] == "unavailable"
    assert missing["reason_code"] == "snapshot_missing"

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json")
    assert module.read_daily_status(invalid, NOW)["reason_code"] == "snapshot_invalid"

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"state":"success","state":"running"}')
    assert module.read_daily_status(duplicate, NOW)["reason_code"] == "snapshot_invalid"

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (module.MAX_STATUS_BYTES + 1))
    assert module.read_daily_status(oversized, NOW)["reason_code"] == "snapshot_invalid"


def test_read_adapter_reads_valid_fixture(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps(snapshot()))
    assert load_module().read_daily_status(path, NOW)["state"] == "success"


def test_module_import_has_no_side_effects(monkeypatch):
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: pytest.fail("opened a file"))
    load_module()
