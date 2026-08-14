from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
import uuid
import zipfile
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_collector():
    spec = importlib.util.spec_from_file_location("wb_async_report", ROOT / "tools" / "wb_async_report.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["wb_async_report"] = module
    spec.loader.exec_module(module)
    return module


def zip_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("detail.csv", "nmID,dt,ordersCount\n123,2026-08-03,2\n")
    return output.getvalue()


class FakeRepository:
    def __init__(self, collector, *, quota_used: int = 0) -> None:
        self.collector = collector
        self.quota_used = quota_used
        self.task = None
        self.raw = []
        self.events: list[str] = []
        self.fail_persist_once = False

    def reserve_task(self, tenant_id, period_from, period_to, quota_date):
        if self.task is not None:
            return self.task, False
        if self.quota_used >= self.collector.DAILY_REPORT_QUOTA:
            raise self.collector.QuotaExhausted("daily report quota exhausted")
        task_id = uuid.uuid4()
        self.quota_used += 1
        self.task = self.collector.TaskRecord(
            task_id=task_id,
            tenant_id=tenant_id,
            period_from=period_from,
            period_to=period_to,
            request_body=self.collector.build_request(task_id, tenant_id, period_from, period_to),
            lifecycle_status="RESERVED",
            api_status=None,
            consecutive_not_found=0,
            create_replay_count=0,
            regenerate_count=0,
        )
        self.events.append("reserve")
        return self.task, True

    def get_task(self, task_id):
        assert self.task is not None and self.task.task_id == task_id
        return self.task

    def mark_initial_create_sent(self, task_id):
        self.task = replace(self.get_task(task_id), lifecycle_status="CREATE_IN_FLIGHT")
        self.events.append("mark:create")
        return self.task

    def reserve_followup_post(self, task_id, action, quota_date):
        task = self.get_task(task_id)
        if self.quota_used >= self.collector.DAILY_REPORT_QUOTA:
            raise self.collector.QuotaExhausted("daily report quota exhausted")
        self.quota_used += 1
        if action == "create_replay":
            self.task = replace(
                task,
                lifecycle_status="CREATE_IN_FLIGHT",
                consecutive_not_found=0,
                create_replay_count=task.create_replay_count + 1,
            )
        else:
            self.task = replace(
                task,
                lifecycle_status="REGENERATE_IN_FLIGHT",
                consecutive_not_found=0,
                regenerate_count=task.regenerate_count + 1,
            )
        self.events.append(f"reserve:{action}")
        return self.task

    def persist_raw(self, envelope):
        if self.fail_persist_once:
            self.fail_persist_once = False
            raise RuntimeError("database unavailable")
        if all(item.response_id != envelope.response_id for item in self.raw):
            self.raw.append(envelope)
        self.events.append(f"raw:{envelope.stage}:{envelope.http_status}")

    def set_status(self, task_id, lifecycle_status, *, api_status=None, error_code=None):
        task = self.get_task(task_id)
        self.task = replace(
            task,
            lifecycle_status=lifecycle_status,
            api_status=api_status or task.api_status,
            consecutive_not_found=0,
        )
        self.events.append(f"status:{lifecycle_status}")
        return self.task

    def increment_not_found(self, task_id):
        task = self.get_task(task_id)
        self.task = replace(task, consecutive_not_found=task.consecutive_not_found + 1)
        self.events.append("status:not-found")
        return self.task

    def complete_download(self, task_id, sha256, byte_size, downloaded_at):
        task = self.get_task(task_id)
        self.task = replace(
            task,
            lifecycle_status="DOWNLOADED",
            api_status="SUCCESS",
            downloaded_sha256=sha256,
            downloaded_size=byte_size,
        )
        self.events.append("status:DOWNLOADED")
        return self.task

    def record_error(self, task_id, error_code):
        self.get_task(task_id)
        self.events.append(f"error:{error_code}")


NOW = datetime.fromisoformat("2026-08-13T12:00:00+03:00")
PERIOD_FROM = date.fromisoformat("2026-08-03")
PERIOD_TO = date.fromisoformat("2026-08-09")


def make_runner(collector, tmp_path, repository, handler, delays):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    recorder = collector.DurableRawRecorder(tmp_path / "spool", repository)
    runner = collector.AsyncReportCollector(
        repository,
        recorder,
        client,
        "header.payload.signature",
        now=lambda: NOW,
        monotonic=lambda: 0.0,
        sleep=delays.append,
        max_wait_seconds=60,
    )
    return runner, client


def test_waiting_processing_retry_are_polled_without_retry_post(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)
    statuses = iter(["WAITING", "PROCESSING", "RETRY", "SUCCESS"])
    requests: list[httpx.Request] = []
    archive = zip_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert repository.task is not None
            assert repository.task.lifecycle_status == "CREATE_IN_FLIGHT"
            assert request.read()
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=archive, headers={"Content-Type": "application/zip"})
        status = next(statuses)
        return httpx.Response(200, json={"data": [{"id": str(repository.task.task_id), "status": status}]})

    delays: list[float] = []
    runner, client = make_runner(collector, tmp_path, repository, handler, delays)
    try:
        result = runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert result.lifecycle_status == "DOWNLOADED"
    assert result.downloaded_size == len(archive)
    assert [request.url.path for request in requests].count("/api/v2/nm-report/downloads/retry") == 0
    assert [item.stage for item in repository.raw] == ["create", "status", "status", "status", "status", "download"]
    download = repository.raw[-1]
    assert base64.b64decode(download.payload["body_base64"]) == archive
    assert repository.events.index("raw:create:200") < repository.events.index("status:WAITING")
    assert delays == [21, 21, 21, 21]


def test_three_404s_replay_create_with_same_uuid(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)
    requests: list[httpx.Request] = []
    status_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal status_calls
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=zip_bytes())
        status_calls += 1
        if status_calls <= 3:
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json={"data": [{"id": str(repository.task.task_id), "status": "SUCCESS"}]})

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        result = runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    create_requests = [request for request in requests if request.method == "POST"]
    ids = [json.loads(request.read())["id"] for request in create_requests]
    assert result.lifecycle_status == "DOWNLOADED"
    assert len(create_requests) == 2
    assert ids == [str(result.task_id), str(result.task_id)]
    assert repository.quota_used == 2


def test_failed_uses_official_regenerate_but_retry_status_only_waits(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)
    statuses = iter(["FAILED", "RETRY", "SUCCESS"])
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.method == "POST" and request.url.path.endswith("/retry"):
            return httpx.Response(200, json={"data": "Retry"})
        if request.method == "POST":
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=zip_bytes())
        return httpx.Response(200, json={"data": [{"id": str(repository.task.task_id), "status": next(statuses)}]})

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        result = runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert result.lifecycle_status == "DOWNLOADED"
    assert paths.count("/api/v2/nm-report/downloads/retry") == 1
    assert repository.quota_used == 2


def test_raw_is_spooled_and_committed_before_invalid_json_is_parsed(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", headers={"Content-Type": "application/json"})

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        with pytest.raises(collector.WbAsyncReportError, match="not valid JSON"):
            runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert len(repository.raw) == 1
    assert base64.b64decode(repository.raw[0].payload["body_base64"]) == b"not-json"
    assert list((tmp_path / "spool").glob("*.json")) == []


def test_database_failure_leaves_durable_spool_for_idempotent_recovery(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)
    task, _ = repository.reserve_task("amirova-test", PERIOD_FROM, PERIOD_TO, PERIOD_TO)
    repository.fail_persist_once = True
    recorder = collector.DurableRawRecorder(tmp_path / "spool", repository)
    response = httpx.Response(200, content=b'{"data":"Created"}')

    with pytest.raises(RuntimeError, match="database unavailable"):
        recorder.capture(task.task_id, "create", response, NOW)

    assert len(list((tmp_path / "spool").glob("*.json"))) == 1
    assert recorder.recover() == 1
    assert len(repository.raw) == 1
    assert recorder.recover() == 0


def test_quota_exhaustion_happens_before_uuid_or_network_request(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector, quota_used=collector.DAILY_REPORT_QUOTA)
    network_calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        return httpx.Response(500)

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        with pytest.raises(collector.QuotaExhausted):
            runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert repository.task is None
    assert network_calls == 0


def test_latest_closed_week_uses_moscow_calendar() -> None:
    collector = load_collector()
    assert collector.latest_closed_week(NOW) == (PERIOD_FROM, PERIOD_TO)


def test_analytics_token_must_be_personal_read_only_and_scoped() -> None:
    collector = load_collector()

    def token(mask: int) -> str:
        def encode(value: object) -> str:
            return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

        return f"{encode({'alg': 'none'})}.{encode({'acc': 3, 'for': 'self', 't': False, 's': mask, 'exp': 1800000000})}.signature"

    valid_mask = (1 << 2) | (1 << 30)
    collector.validate_analytics_token(token(valid_mask), now=NOW)
    with pytest.raises(collector.WbAsyncReportError, match="Analytics"):
        collector.validate_analytics_token(token(1 << 30), now=NOW)
    with pytest.raises(collector.WbAsyncReportError, match="read-only"):
        collector.validate_analytics_token(token(1 << 2), now=NOW)


def test_analytics_rw_token_requires_explicit_opt_in() -> None:
    collector = load_collector()

    def token(mask: int, *, acc: int = 3, exp: int = 1800000000) -> str:
        def encode(value: object) -> str:
            return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

        return f"{encode({'alg': 'none'})}.{encode({'acc': acc, 'for': 'self', 't': False, 's': mask, 'exp': exp})}.signature"

    rw_analytics = 1 << 2
    with pytest.raises(collector.WbAsyncReportError, match="read-only"):
        collector.validate_analytics_token(token(rw_analytics), now=NOW)
    collector.validate_analytics_token(token(rw_analytics), now=NOW, allow_read_write=True)
    with pytest.raises(collector.WbAsyncReportError, match="Analytics"):
        collector.validate_analytics_token(token(0), now=NOW, allow_read_write=True)
    with pytest.raises(collector.WbAsyncReportError, match="only the Analytics category"):
        collector.validate_analytics_token(token(rw_analytics | (1 << 3)), now=NOW, allow_read_write=True)
    with pytest.raises(collector.WbAsyncReportError, match="only the Analytics category"):
        collector.validate_analytics_token(token(rw_analytics | (1 << 3) | (1 << 30)), now=NOW)
    with pytest.raises(collector.WbAsyncReportError, match="personal"):
        collector.validate_analytics_token(token(rw_analytics, acc=1), now=NOW, allow_read_write=True)
    with pytest.raises(collector.WbAsyncReportError, match="expired"):
        collector.validate_analytics_token(token(rw_analytics, exp=1), now=NOW, allow_read_write=True)
    args = collector.parse_args(["--tenant-id", "amirova-test"])
    assert args.allow_analytics_read_write is False
    enabled = collector.parse_args(["--tenant-id", "amirova-test", "--allow-analytics-read-write"])
    assert enabled.allow_analytics_read_write is True
    with pytest.raises(SystemExit):
        collector.parse_args(["--tenant-id", "amirova-test", "--allow"])
