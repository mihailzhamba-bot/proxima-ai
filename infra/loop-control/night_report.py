#!/usr/bin/env python3
"""One scheduled evidence report; native notifier owns Telegram delivery."""
from __future__ import annotations
import base64
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
import uuid
from zoneinfo import ZoneInfo
from datetime import datetime
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

CONFIG = Path("/etc/loop/night-report.json")
DATABASE = "/var/lib/loop/bridge/bridge.sqlite"
CONTAINER = "loop-control-bridge-1"
OPERATOR_SECRET = Path("/etc/loop/secrets/bridge_operator")


def validate(config):
    if set(config) != {"batch_id", "label", "tasks", "report_at"}:
        raise ValueError("fixed report config required")
    if not isinstance(config["batch_id"], str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,120}", config["batch_id"]):
        raise ValueError("invalid batch identity")
    if not isinstance(config["label"], str) or not 0 < len(config["label"]) <= 160:
        raise ValueError("invalid report label")
    if not isinstance(config["tasks"], list) or not 1 <= len(config["tasks"]) <= 3:
        raise ValueError("one to three fixed tasks required")
    for task in config["tasks"]:
        if not {"job_id", "label"} <= set(task) or set(task) - {"job_id", "label", "parent_run_id"} or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", task["job_id"]) or not isinstance(task["label"], str) or not 0 < len(task["label"]) <= 160:
            raise ValueError("invalid fixed task")
        if "parent_run_id" in task:
            if str(uuid.UUID(task["parent_run_id"])) != task["parent_run_id"]:
                raise ValueError("canonical parent UUID required")
    if len({task["job_id"] for task in config["tasks"]}) != len(config["tasks"]):
        raise ValueError("duplicate fixed task")
    at = datetime.fromisoformat(config["report_at"])
    if at.tzinfo is None:
        raise ValueError("report_at timezone required")
    return at.timestamp()


def snapshot(db, config):
    db.row_factory = sqlite3.Row
    tasks = []
    for task in config["tasks"]:
        parents = []
        for row in db.execute("SELECT * FROM operations WHERE kind='paperclip' ORDER BY created DESC"):
            request = json.loads(row["request"])
            explicit = task.get("parent_run_id")
            bound = row["id"] == explicit if explicit else ((row["key"] == config["batch_id"] or row["key"].startswith(config["batch_id"] + "-")) and request.get("source") == "operator_batch")
            if bound and request.get("source") in {"operator_batch", "native_telegram"} and request.get("job_id") == task["job_id"]:
                parents.append(dict(row))
        parent = parents[0] if parents else None
        child = db.execute("SELECT * FROM operations WHERE kind='hermes' AND key=?", (parent["external_id"],)).fetchone() if parent and parent["external_id"] else None
        job = db.execute("SELECT * FROM jobs WHERE id=? AND director_run=?", (task["job_id"], child["id"])).fetchone() if child else None
        tasks.append({**task, "parent": parent, "child": dict(child) if child else None, "job": dict(job) if job else None})
    paused = db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()
    return {"tasks": tasks, "paused": paused[0] if paused else "unknown", "snapshot_at": time.time()}


def verification(job):
    try:
        report = json.loads(job.get("verification") or "{}")
    except (ValueError, TypeError):
        report = {}
    sha = job.get("candidate_sha")
    checks = report.get("checks", {})
    statuses = []
    accepted = report.get("producer") == "harper" and bool(sha) and report.get("sha") == sha
    for name in ("verify", "build", "review"):
        check = checks.get(name, {}) if isinstance(checks, dict) else {}
        passed = isinstance(check, dict) and check.get("sha") == sha and check.get("status") == "pass" and check.get("skipped") == 0
        accepted = accepted and passed
        statuses.append(name + " " + ("pass" if passed else "не подтверждён"))
    return accepted, ", ".join(statuses)


def format_report(config, data, now=None, refresh_errors=0):
    now = time.time() if now is None else now
    lines = ["Утренний отчёт LOOP / Директор", config["label"], datetime.fromtimestamp(now, ZoneInfo("Europe/Moscow")).isoformat(timespec="seconds")]
    for index, task in enumerate(data["tasks"], 1):
        job, parent, child = task["job"], task["parent"], task["child"]
        accepted, checks = verification(job or {})
        state = job["state"] if job else (child or parent or {}).get("state", "not_started")
        if job and state == "ready_pr" and accepted and re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*", job.get("pr_url") or ""):
            result = "готов PR\n" + job["pr_url"]
        elif state == "ready_pr":
            result = "готовность PR не подтверждена"
        elif state in {"failed", "error", "rejected"}:
            result = "ошибка"
        elif state in {"cancelled", "cancelling", "interrupted", "stopped"}:
            result = "остановлена"
        elif state == "not_started":
            result = "не запускалась"
        elif state == "completed" and not job:
            result = "запуск завершился, задача не создана"
        else:
            result = "статус " + state
        observed = (child or parent or {}).get("updated")
        observed_text = " Статус наблюдали " + str(max(0, int(now - observed))) + " сек. назад." if observed is not None else ""
        lines.extend([str(index) + ". " + task["label"] + ": " + result + observed_text, "Проверки: " + checks])
    queue = {"true": "на паузе", "false": "доступна"}.get(data["paused"], "статус неизвестен")
    age = max(0, int(now - data["snapshot_at"]))
    lines.extend(["Очередь " + queue + ". Источник: сохранённый Bridge, снимок " + str(age) + " сек. назад.",
                  "Актуальность данных WB и готовность WB-сводки не подтверждены. Merge и deploy не выполнялись."])
    if refresh_errors:
        lines.append("Не удалось обновить " + str(refresh_errors) + " статусов; показаны сохранённые данные.")
    return "\n".join(lines)


def enqueue(db, batch_id, text, now=None):
    identity = hashlib.sha256(batch_id.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO native_notifications(id,text,created,state,run_id) VALUES(?,?,?,'pending',NULL)", (identity, text, time.time() if now is None else now))
    row = db.execute("SELECT state FROM native_notifications WHERE id=?", (identity,)).fetchone()
    return {"notification_id": identity, "state": row[0], "delivery_confirmed": row[0] == "delivered"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect denied")


def refresh(data):
    token = OPERATOR_SECRET.read_text().strip()
    if not token or OPERATOR_SECRET.stat().st_mode & 0o077:
        raise ValueError("operator credential unavailable")
    errors = 0
    for task in data["tasks"]:
        for operation in (task["parent"], task["child"]):
            if not operation or not operation["external_id"] or operation["state"] in {"cancelled", "cancelling"}:
                continue
            request = Request("http://127.0.0.1:18770/v1/runs/" + operation["id"], headers={"Authorization": "Bearer " + token})
            try:
                with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=4) as response:
                    json.loads(response.read(100000))
            except Exception:
                errors += 1
    return errors


def container_call(config, action, refresh_errors=0):
    payload = base64.b64encode(json.dumps({"config": config, "action": action, "refresh_errors": refresh_errors}).encode()).decode()
    completed = subprocess.run(["docker", "exec", "-i", "--user", "10001", CONTAINER, "python3", "-", "--container", payload], input=Path(__file__).read_text(), text=True, capture_output=True, timeout=20, check=True)
    return json.loads(completed.stdout)


def container_main(payload):
    config = payload["config"]
    validate(config)
    with sqlite3.connect(DATABASE, timeout=5) as db:
        db.execute("BEGIN IMMEDIATE")
        data = snapshot(db, config)
        if payload["action"] == "snapshot":
            return data
        if payload["action"] != "enqueue":
            raise ValueError("invalid report action")
        return enqueue(db, config["batch_id"], format_report(config, data, refresh_errors=payload["refresh_errors"]))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--container":
        result = container_main(json.loads(base64.b64decode(sys.argv[2])))
    else:
        config = json.loads(CONFIG.read_text())
        if time.time() < validate(config):
            raise ValueError("report is not due")
        data = container_call(config, "snapshot")
        try:
            errors = refresh(data)
        except Exception:
            errors = sum(bool(task[part]) for task in data["tasks"] for part in ("parent", "child"))
        result = container_call(config, "enqueue", errors)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("night report unavailable; native delivery not confirmed", file=sys.stderr)
        raise SystemExit(1) from None
