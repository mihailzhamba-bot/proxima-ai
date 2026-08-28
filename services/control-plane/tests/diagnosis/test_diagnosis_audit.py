import json

from proxima_control_plane.diagnosis.audit import AuditLog


def test_record_appends_one_jsonl_line_per_call(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record({"outcome": "ok", "attempts": 1})
    log.record({"outcome": "failed", "attempts": 3})
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"outcome": "ok", "attempts": 1}
    assert json.loads(lines[1]) == {"outcome": "failed", "attempts": 3}


def test_record_creates_parent_dirs(tmp_path):
    log = AuditLog(tmp_path / "a" / "b" / "audit.jsonl")
    log.record({"outcome": "ok"})
    assert (tmp_path / "a" / "b" / "audit.jsonl").is_file()


def test_record_swallows_unwritable_target(tmp_path):
    log = AuditLog(tmp_path)
    log.record({"outcome": "ok"})
