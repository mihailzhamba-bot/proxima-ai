import importlib.util
import json
import sqlite3
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("night_report", ROOT / "infra/loop-control/night_report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)
CONFIG = {"batch_id": "night-20260915", "label": "Ночные задачи", "tasks": [{"job_id": "night-probe-001", "label": "Проверка"}], "report_at": "2026-09-16T08:00:00+03:00"}


def database():
    db = sqlite3.connect(":memory:")
    db.executescript("""CREATE TABLE operations(id TEXT,kind TEXT,key TEXT,request TEXT,external_id TEXT,state TEXT,created REAL,updated REAL);
        CREATE TABLE jobs(id TEXT,director_run TEXT,state TEXT,verification TEXT,candidate_sha TEXT,pr_url TEXT);
        CREATE TABLE settings(key TEXT,value TEXT);
        INSERT INTO settings VALUES('paused','true');
        CREATE TABLE native_notifications(id TEXT PRIMARY KEY,text TEXT,state TEXT,created REAL,run_id TEXT);""")
    return db


def task_data(job=None, parent=None, child=None):
    return {"tasks": [{**CONFIG["tasks"][0], "job": job, "parent": parent, "child": child}], "paused": "true", "snapshot_at": 90}


def ready_job():
    sha = "a" * 40
    verification = {"producer": "harper", "sha": sha, "checks": {name: {"sha": sha, "status": "pass", "skipped": 0} for name in ("verify", "build", "review")}}
    return {"state": "ready_pr", "candidate_sha": sha, "verification": json.dumps(verification), "pr_url": "https://github.com/fixture/repo/pull/1"}


def test_missing_and_unknown_are_honest_with_source_age():
    text = report.format_report(CONFIG, task_data(), now=100)
    assert "не запускалась" in text and "10 сек." in text and "Очередь на паузе" in text
    assert "готов PR" not in text
    text = report.format_report(CONFIG, task_data(parent={"state": "unknown", "updated": 20}), now=100, refresh_errors=1)
    assert "статус unknown" in text and "80 сек." in text and "сохранённые данные" in text
    assert "WB-сводки не подтверждены" in text


@pytest.mark.parametrize("change", ["missing", "skipped", "sha", "producer", "url"])
def test_ready_pr_requires_all_trusted_checks_and_valid_link(change):
    job = ready_job()
    verification = json.loads(job["verification"])
    if change == "missing":
        verification["checks"].pop("review")
    elif change == "skipped":
        verification["checks"]["build"]["skipped"] = 1
    elif change == "sha":
        verification["checks"]["verify"]["sha"] = "b" * 40
    elif change == "producer":
        verification["producer"] = "director"
    else:
        job["pr_url"] = "http://fake.example/pr"
    job["verification"] = json.dumps(verification)
    text = report.format_report(CONFIG, task_data(job=job), now=100)
    assert "готовность PR не подтверждена" in text
    assert job["pr_url"] not in text


def test_ready_pr_links_and_checks_are_reported():
    job = ready_job()
    text = report.format_report(CONFIG, task_data(job=job), now=100)
    assert "готов PR" in text and job["pr_url"] in text
    assert "verify pass, build pass, review pass" in text


@pytest.mark.parametrize("state", ["pending", "delivered", "delivery_unknown", "sending"])
def test_enqueue_idempotency_preserves_delivery_state_and_original_text(state):
    db = database()
    first = report.enqueue(db, CONFIG["batch_id"], "original", now=100)
    db.execute("UPDATE native_notifications SET state=?", (state,))
    second = report.enqueue(db, CONFIG["batch_id"], "changed", now=200)
    assert first["notification_id"] == second["notification_id"]
    assert second["state"] == state and second["delivery_confirmed"] == (state == "delivered")
    assert db.execute("SELECT text,created,run_id FROM native_notifications").fetchone() == ("original", 100, None)
    assert db.execute("SELECT count(*) FROM native_notifications").fetchone()[0] == 1


def add_attempt(db, parent, key, source="operator_batch", job=True):
    db.execute("INSERT INTO operations VALUES(?, 'paperclip', ?, ?, ?, 'completed', 1, 20)", (parent, key, json.dumps({"source": source, "job_id": "night-probe-001"}), parent + "-external"))
    db.execute("INSERT INTO operations VALUES(?, 'hermes', ?, '{}', 'hermes-external', 'completed', 2, 30)", (parent + "-child", parent + "-external"))
    if job:
        db.execute("INSERT INTO jobs VALUES('night-probe-001', ?, 'ready_pr', NULL, NULL, 'old-pr')", (parent + "-child",))


def test_snapshot_never_uses_older_job_with_same_identifier():
    db = database()
    add_attempt(db, "old", "other-batch-probe")
    add_attempt(db, "current", "night-20260915-probe", job=False)
    data = report.snapshot(db, CONFIG)
    assert data["tasks"][0]["parent"]["id"] == "current"
    assert data["tasks"][0]["job"] is None


def test_explicit_native_parent_is_exact_and_no_fallback_to_old_job():
    db = database()
    parent = "11111111-1111-4111-8111-111111111111"
    add_attempt(db, "old", "native-telegram-old", source="native_telegram")
    add_attempt(db, parent, "native-retry-old", source="native_telegram", job=False)
    config = {**CONFIG, "tasks": [{**CONFIG["tasks"][0], "parent_run_id": parent}]}
    report.validate(config)
    data = report.snapshot(db, config)
    assert data["tasks"][0]["parent"]["id"] == parent and data["tasks"][0]["job"] is None
    config["tasks"][0]["parent_run_id"] = "22222222-2222-4222-8222-222222222222"
    assert report.snapshot(db, config)["tasks"][0]["parent"] is None


def test_timer_and_service_are_fixed_and_bounded():
    timer = (ROOT / "infra/loop-control/loop-night-report.timer").read_text()
    service = (ROOT / "infra/loop-control/loop-night-report.service").read_text()
    assert "OnCalendar=2026-09-16 08:00:00 Europe/Moscow" in timer and "Persistent=true" in timer
    assert "TimeoutStartSec=90s" in service and "User=root" in service
