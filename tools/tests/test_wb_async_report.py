from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
import uuid
import zipfile
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]
# Anonymized `GET nm-report/downloads` list (two reports created 29/30.08.2026 UTC).
DOWNLOADS_LIST_FIXTURE = ROOT / "services" / "collector" / "tests" / "fixtures" / "wb-api" / "analytics" / "nm_report_downloads" / "sample.json"


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
    def __init__(self, collector, *, quota_used: int = 0, tenants: tuple[str, ...] = ("amirova-test",)) -> None:
        self.collector = collector
        self.quota_used = quota_used
        self.tenants = set(tenants)
        self.task = None
        self.raw = []
        self.runs: list[dict[str, object]] = []
        self.events: list[str] = []
        self.fail_persist_once = False
        self.fail_stage_mismatch_once = False
        self.fail_close_run_once = False
        self.staged_rows: list[dict[str, str]] = []

    def _require_tenant(self, tenant_id):
        if tenant_id not in self.tenants:
            raise self.collector.WbAsyncReportError(f"tenant {tenant_id} does not exist: the collector never creates tenants (AD-5)")

    def open_run(self, tenant_id, kind, *, git_sha=None, image_id=None):
        self._require_tenant(tenant_id)
        run_id = uuid.uuid4()
        self.runs.append({"run_id": run_id, "tenant_id": tenant_id, "kind": kind, "status": "RUNNING", "finished_at": None, "git_sha": git_sha, "image_id": image_id})
        self.events.append("run:RUNNING")
        return run_id

    def close_run(self, run_id, status):
        if self.fail_close_run_once:
            self.fail_close_run_once = False
            raise RuntimeError("database unavailable")
        for run in self.runs:
            if run["run_id"] == run_id and run["status"] == "RUNNING":
                run["status"] = status
                run["finished_at"] = NOW
                self.events.append(f"run:{status}")
                return
        raise self.collector.WbAsyncReportError(f"cannot mark run {run_id} {status}: expected one RUNNING row, updated 0")

    def reserve_task(self, tenant_id, period_from, period_to, quota_date, collector_run_id):
        self._require_tenant(tenant_id)
        if self.task is not None:
            if self.task.lifecycle_status != "DOWNLOADED":
                self.task = replace(self.task, collector_run_id=collector_run_id)
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
            collector_run_id=collector_run_id,
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

    def complete_download(self, task_id, sha256, byte_size, downloaded_at, rows):
        task = self.get_task(task_id)
        if self.fail_stage_mismatch_once:
            self.fail_stage_mismatch_once = False
            raise self.collector.RowCountMismatch(f"parsed {len(rows)} report rows but staged 0 for task {task_id}")
        self.staged_rows = list(rows)
        self.task = replace(
            task,
            lifecycle_status="DOWNLOADED",
            api_status="SUCCESS",
            downloaded_sha256=sha256,
            downloaded_size=byte_size,
            parsed_row_count=len(rows),
            staged_row_count=len(rows),
        )
        self.events.append("status:DOWNLOADED")
        return self.task

    def record_error(self, task_id, error_code):
        self.get_task(task_id)
        self.events.append(f"error:{error_code}")


NOW = datetime.fromisoformat("2026-08-13T12:00:00+03:00")
PERIOD_FROM = date.fromisoformat("2026-08-03")
PERIOD_TO = date.fromisoformat("2026-08-09")


def is_list_request(request: httpx.Request) -> bool:
    """The daily guard's unfiltered `GET nm-report/downloads`; status polls carry `filter[downloadIds]`."""
    return request.method == "GET" and request.url.path.endswith("/nm-report/downloads") and "filter[downloadIds]" not in request.url.params


def list_response() -> httpx.Response:
    return httpx.Response(200, content=DOWNLOADS_LIST_FIXTURE.read_bytes(), headers={"Content-Type": "application/json"})


def make_runner(collector, tmp_path, repository, handler, delays, *, now: datetime = NOW):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    recorder = collector.DurableRawRecorder(tmp_path / "spool", repository)
    runner = collector.AsyncReportCollector(
        repository,
        recorder,
        client,
        "header.payload.signature",
        now=lambda: now,
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
        if is_list_request(request):
            return list_response()
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
    assert result.parsed_row_count == 1
    assert result.staged_row_count == 1
    assert repository.staged_rows == [{"nmID": "123", "dt": "2026-08-03", "ordersCount": "2"}]
    assert [request.url.path for request in requests].count("/api/v2/nm-report/downloads/retry") == 0
    # the daily guard's list answer is captured first, with stage `status`
    assert [item.stage for item in repository.raw] == ["status", "create", "status", "status", "status", "status", "download"]
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
        if is_list_request(request):
            return list_response()
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
        if is_list_request(request):
            return list_response()
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


def test_download_without_csv_blocks_with_parse_error(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("detail.txt", "not a csv")

    def handler(request: httpx.Request) -> httpx.Response:
        if is_list_request(request):
            return list_response()
        if request.method == "POST":
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=output.getvalue(), headers={"Content-Type": "application/zip"})
        return httpx.Response(200, json={"data": [{"id": str(repository.task.task_id), "status": "SUCCESS"}]})

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        with pytest.raises(collector.WbAsyncReportError, match="exactly one CSV"):
            runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert repository.task is not None
    assert repository.task.lifecycle_status == "BLOCKED"
    assert repository.staged_rows == []
    # the ledger run of a blocked task is closed FAILED, never left RUNNING
    assert [run["status"] for run in repository.runs] == ["FAILED"]


def test_row_count_mismatch_blocks_task_instead_of_reporting_success(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)
    repository.fail_stage_mismatch_once = True

    def handler(request: httpx.Request) -> httpx.Response:
        if is_list_request(request):
            return list_response()
        if request.method == "POST":
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=zip_bytes(), headers={"Content-Type": "application/zip"})
        return httpx.Response(200, json={"data": [{"id": str(repository.task.task_id), "status": "SUCCESS"}]})

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        with pytest.raises(collector.RowCountMismatch):
            runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert repository.task is not None
    assert repository.task.lifecycle_status == "BLOCKED"
    assert "status:BLOCKED" in repository.events


def test_parse_report_rows_is_fail_closed_on_malformed_rows() -> None:
    collector = load_collector()

    def archive_with(csv_text: str) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("detail.csv", csv_text)
        return output.getvalue()

    assert collector.parse_report_rows(archive_with("nmID,dt,ordersCount\n123,2026-08-03,2\n")) == [
        {"nmID": "123", "dt": "2026-08-03", "ordersCount": "2"}
    ]
    with pytest.raises(collector.WbAsyncReportError, match="does not match the header"):
        collector.parse_report_rows(archive_with("nmID,dt\n123,2026-08-03,extra\n"))
    with pytest.raises(collector.WbAsyncReportError, match="does not match the header"):
        collector.parse_report_rows(archive_with("nmID,dt,ordersCount\n123,2026-08-03\n"))
    with pytest.raises(collector.WbAsyncReportError, match="no valid header"):
        collector.parse_report_rows(archive_with(""))


def test_raw_is_spooled_and_committed_before_invalid_json_is_parsed(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)

    def handler(request: httpx.Request) -> httpx.Response:
        if is_list_request(request):
            return list_response()
        return httpx.Response(200, content=b"not-json", headers={"Content-Type": "application/json"})

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        with pytest.raises(collector.WbAsyncReportError, match="not valid JSON"):
            runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert [item.stage for item in repository.raw] == ["status", "create"]
    assert base64.b64decode(repository.raw[-1].payload["body_base64"]) == b"not-json"
    assert list((tmp_path / "spool").glob("*.json")) == []


def test_database_failure_leaves_durable_spool_for_idempotent_recovery(tmp_path: Path) -> None:
    collector = load_collector()
    repository = FakeRepository(collector)
    task, _ = repository.reserve_task("amirova-test", PERIOD_FROM, PERIOD_TO, PERIOD_TO, uuid.uuid4())
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
    with pytest.raises(collector.WbAsyncReportError, match="only the Analytics category"):
        collector.validate_analytics_token(token(rw_analytics | (1 << 8) | (1 << 30)), now=NOW)
    with pytest.raises(collector.WbAsyncReportError, match="only the Analytics category"):
        collector.validate_analytics_token(token(rw_analytics | (1 << 31)), now=NOW, allow_read_write=True)
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


# --- Story 3.2: run ledger, tenant fail-closed, explicit period, daily guard ---


def happy_path_handler(repository):
    def handler(request: httpx.Request) -> httpx.Response:
        if is_list_request(request):
            return list_response()
        if request.method == "POST":
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=zip_bytes(), headers={"Content-Type": "application/zip"})
        return httpx.Response(200, json={"data": [{"id": str(repository.task.task_id), "status": "SUCCESS"}]})

    return handler


def ledger_lines(stderr: str) -> list[dict]:
    return [json.loads(line) for line in stderr.splitlines() if line.startswith("{")]


def test_missing_tenant_fails_closed_before_any_run_row_or_network(tmp_path: Path) -> None:
    """AC: no tenant -> error. Nothing is written (no run row, no task) and WB
    is never called; the tool does not create the tenant itself (AD-5)."""
    collector = load_collector()
    repository = FakeRepository(collector, tenants=())
    network_calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        return list_response()

    runner, client = make_runner(collector, tmp_path, repository, handler, [])
    try:
        with pytest.raises(collector.WbAsyncReportError, match="tenant ghost-tenant does not exist"):
            runner.collect("ghost-tenant", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()

    assert repository.runs == []
    assert repository.task is None
    assert repository.events == []
    assert network_calls == 0
    assert runner.run_id is None


def test_run_is_opened_running_and_closed_succeeded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AC: the run exists RUNNING before any work and is SUCCEEDED with
    finished_at after the download; the task carries the run as its
    collector_run_id; the ledger events are the first and the last things."""
    collector = load_collector()
    repository = FakeRepository(collector)
    runner, client = make_runner(collector, tmp_path, repository, happy_path_handler(repository), [])
    try:
        result = runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO, git_sha="0902688", image_id="sha256:fixture")
    finally:
        client.close()

    assert result.lifecycle_status == "DOWNLOADED"
    assert len(repository.runs) == 1
    run = repository.runs[0]
    assert run["tenant_id"] == "amirova-test"
    assert run["kind"] == "funnel_csv_download"
    assert run["status"] == "SUCCEEDED"
    assert run["finished_at"] is not None
    assert (run["git_sha"], run["image_id"]) == ("0902688", "sha256:fixture")
    assert result.collector_run_id == run["run_id"] == runner.run_id
    assert repository.events[0] == "run:RUNNING"
    assert repository.events[-1] == "run:SUCCEEDED"
    assert repository.events.index("status:DOWNLOADED") < repository.events.index("run:SUCCEEDED")

    captured = capsys.readouterr()
    assert captured.out == ""
    lines = ledger_lines(captured.err)
    assert [line["event"] for line in lines if "event" in line] == ["run-ledger:running", "run-ledger:succeeded"]
    assert all(line["kind"] == "funnel_csv_download" and line["run_id"] == str(runner.run_id) for line in lines)
    assert "header.payload.signature" not in captured.err


def test_failed_run_is_closed_failed_and_the_original_error_surfaces(tmp_path: Path) -> None:
    collector = load_collector()

    def denied_create(request: httpx.Request) -> httpx.Response:
        if is_list_request(request):
            return list_response()
        if request.method == "POST":
            return httpx.Response(403, json={"detail": "forbidden"})
        raise AssertionError("no request may follow a denied create")

    repository = FakeRepository(collector)
    runner, client = make_runner(collector, tmp_path / "first", repository, denied_create, [])
    try:
        with pytest.raises(collector.WbAsyncReportError, match="create failed with HTTP 403"):
            runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()
    assert [run["status"] for run in repository.runs] == ["FAILED"]
    assert repository.runs[0]["finished_at"] is not None
    assert repository.task is not None and repository.task.lifecycle_status == "BLOCKED"
    assert repository.events[-1] == "run:FAILED"

    # A failing FAILED flip must not hide the original error: the run stays
    # RUNNING for Story 1.7's tooling, the collect error is still the one raised.
    stuck = FakeRepository(collector)
    stuck.fail_close_run_once = True
    runner, client = make_runner(collector, tmp_path / "second", stuck, denied_create, [])
    try:
        with pytest.raises(collector.WbAsyncReportError, match="create failed with HTTP 403"):
            runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()
    assert [run["status"] for run in stuck.runs] == ["RUNNING"]


def test_second_run_in_a_day_does_not_create_a_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AC: at most one created report per Moscow day (AD-5), checked against the
    live downloads list. Run 1 creates (the list holds only older reports); run 2
    of the same day, for another period, finds today's report, creates nothing,
    keeps its task RESERVED and still closes SUCCEEDED with a log note; the next
    day the RESERVED task is created without a second reservation."""
    collector = load_collector()
    today = datetime.fromisoformat("2026-09-07T06:30:00+03:00")
    clock = {"now": today}
    wb_reports: list[dict] = list(json.loads(DOWNLOADS_LIST_FIXTURE.read_text(encoding="utf-8"))["data"])
    create_posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal create_posts
        if is_list_request(request):
            return httpx.Response(200, json={"data": wb_reports})
        if request.method == "POST":
            create_posts += 1
            body = json.loads(request.read())
            created_at = clock["now"].astimezone(collector.UTC).strftime("%Y-%m-%d %H:%M:%S")
            wb_reports.insert(0, {"id": body["id"], "status": "SUCCESS", "name": body["userReportName"], "size": 1, "startDate": body["params"]["startDate"], "endDate": body["params"]["endDate"], "createdAt": created_at})
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=zip_bytes(), headers={"Content-Type": "application/zip"})
        return httpx.Response(200, json={"data": [{"id": request.url.params["filter[downloadIds]"], "status": "SUCCESS"}]})

    first = FakeRepository(collector)
    runner, client = make_runner(collector, tmp_path / "first", first, handler, [], now=today)
    try:
        downloaded = runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()
    assert downloaded.lifecycle_status == "DOWNLOADED"
    assert create_posts == 1
    assert [run["status"] for run in first.runs] == ["SUCCEEDED"]

    second = FakeRepository(collector)
    other_from, other_to = date.fromisoformat("2026-08-10"), date.fromisoformat("2026-08-16")
    runner, client = make_runner(collector, tmp_path / "second", second, handler, [], now=today)
    try:
        guarded = runner.collect("amirova-test", other_from, other_to)
    finally:
        client.close()
    assert create_posts == 1
    assert guarded.lifecycle_status == "RESERVED"
    assert "mark:create" not in second.events
    assert [item.stage for item in second.raw] == ["status"]
    assert [run["status"] for run in second.runs] == ["SUCCEEDED"]
    notes = [line for line in ledger_lines(capsys.readouterr().err) if line.get("step") == "daily-report-guard"]
    assert len(notes) == 1
    assert notes[0]["reports_created_today"] == 1
    assert notes[0]["quota_date"] == "2026-09-07"
    assert notes[0]["run_id"] == str(second.runs[0]["run_id"])

    clock["now"] = today + timedelta(days=1)
    runner, client = make_runner(collector, tmp_path / "third", second, handler, [], now=clock["now"])
    try:
        resumed = runner.collect("amirova-test", other_from, other_to)
    finally:
        client.close()
    assert resumed.lifecycle_status == "DOWNLOADED"
    assert create_posts == 2
    assert second.quota_used == 1
    assert [run["status"] for run in second.runs] == ["SUCCEEDED", "SUCCEEDED"]
    assert resumed.collector_run_id == second.runs[1]["run_id"]


def test_unreadable_downloads_list_fails_closed_without_creating(tmp_path: Path) -> None:
    """The guard cannot be skipped: a list that fails or drifts fails the run,
    the task stays RESERVED, nothing is created; 429 waits on the retry header."""
    collector = load_collector()
    cases = (
        ("http-500", httpx.Response(500), "downloads list failed with HTTP 500"),
        ("denied", httpx.Response(403, json={"detail": "forbidden"}), "downloads list failed with HTTP 403"),
        ("drift", httpx.Response(200, json={"items": []}), "schema drift"),
        ("not-json", httpx.Response(200, content=b"not-json", headers={"Content-Type": "application/json"}), "not valid JSON"),
    )
    for name, list_answer, message in cases:
        repository = FakeRepository(collector)
        posts = 0

        def handler(request: httpx.Request, answer: httpx.Response = list_answer) -> httpx.Response:
            nonlocal posts
            if is_list_request(request):
                return answer
            posts += 1
            return httpx.Response(200, json={"data": "Created"})

        runner, client = make_runner(collector, tmp_path / name, repository, handler, [])
        try:
            with pytest.raises(collector.WbAsyncReportError, match=message):
                runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
        finally:
            client.close()
        assert posts == 0, name
        assert repository.task is not None and repository.task.lifecycle_status == "RESERVED", name
        assert [run["status"] for run in repository.runs] == ["FAILED"], name
        assert any(event.startswith("error:LIST_") for event in repository.events), name

    repository = FakeRepository(collector)
    list_calls = 0

    def rate_limited_once(request: httpx.Request) -> httpx.Response:
        nonlocal list_calls
        if is_list_request(request):
            list_calls += 1
            if list_calls == 1:
                return httpx.Response(429, headers={"X-RateLimit-Retry": "30"})
            return list_response()
        return happy_path_handler(repository)(request)

    delays: list[float] = []
    runner, client = make_runner(collector, tmp_path / "rate-limited", repository, rate_limited_once, delays)
    try:
        result = runner.collect("amirova-test", PERIOD_FROM, PERIOD_TO)
    finally:
        client.close()
    assert result.lifecycle_status == "DOWNLOADED"
    assert list_calls == 2
    assert delays[0] == 30
    assert [run["status"] for run in repository.runs] == ["SUCCEEDED"]


def test_reports_created_on_reads_utc_timestamps_into_the_moscow_day() -> None:
    collector = load_collector()
    body = json.loads(DOWNLOADS_LIST_FIXTURE.read_text(encoding="utf-8"))
    # Reports made by another consumer never consume Proxima's daily guard.
    assert collector.reports_created_on(body, date.fromisoformat("2026-08-30"), "amirova-test") == 0
    own = {"data": [{"id": "x", "name": "proxima-amirova-test-2026-08-03-2026-08-09", "createdAt": "2026-08-30 04:17:23"}]}
    assert collector.reports_created_on(own, date.fromisoformat("2026-08-30"), "amirova-test") == 1
    assert collector.reports_created_on(own, date.fromisoformat("2026-08-29"), "amirova-test") == 0
    # 21:30 UTC (D20 reads createdAt as UTC) is already the next Moscow day
    late = {"data": [{"id": "x", "name": "proxima-amirova-test-period", "createdAt": "2026-08-29 21:30:00"}]}
    assert collector.reports_created_on(late, date.fromisoformat("2026-08-30"), "amirova-test") == 1
    assert collector.reports_created_on(late, date.fromisoformat("2026-08-29"), "amirova-test") == 0
    explicit = {"data": [{"id": "x", "name": "proxima-amirova-test-period", "createdAt": "2026-08-30T00:30:00+03:00"}]}
    assert collector.reports_created_on(explicit, date.fromisoformat("2026-08-30"), "amirova-test") == 1
    assert collector.reports_created_on(explicit, date.fromisoformat("2026-08-29"), "amirova-test") == 0
    mixed = {"data": [own["data"][0], {"name": "detail_history_report", "createdAt": "2026-08-30 05:00:00"}]}
    assert collector.reports_created_on(mixed, date.fromisoformat("2026-08-30"), "amirova-test") == 1
    assert collector.reports_created_on({"data": []}, date.fromisoformat("2026-08-30"), "amirova-test") == 0
    with pytest.raises(collector.WbAsyncReportError, match="schema drift"):
        collector.reports_created_on({"data": "x"}, date.fromisoformat("2026-08-30"), "amirova-test")
    with pytest.raises(collector.WbAsyncReportError, match="schema drift"):
        collector.reports_created_on(["not", "an", "object"], date.fromisoformat("2026-08-30"), "amirova-test")
    with pytest.raises(collector.WbAsyncReportError, match="no readable createdAt"):
        collector.reports_created_on({"data": [{"name": "proxima-amirova-test-period", "createdAt": "yesterday"}]}, date.fromisoformat("2026-08-30"), "amirova-test")


def test_parse_period_accepts_explicit_closed_range_and_keeps_latest_closed_week() -> None:
    collector = load_collector()
    assert collector.parse_period("latest-closed-week", NOW) == (PERIOD_FROM, PERIOD_TO)
    assert collector.parse_period("2026-08-03..2026-08-09", NOW) == (PERIOD_FROM, PERIOD_TO)
    single_day = date.fromisoformat("2026-08-12")
    assert collector.parse_period("2026-08-12..2026-08-12", NOW) == (single_day, single_day)
    rejected = (
        ("2026-08-09..2026-08-03", "start must not be after"),
        ("2026-08-10..2026-08-13", "closed day"),
        ("2026-08-13..2026-08-13", "closed day"),
        ("2026-02-30..2026-03-01", "valid ISO"),
        ("last-week", "must be latest-closed-week"),
        ("2026-08-03..", "must be latest-closed-week"),
        ("2026-08-03 2026-08-09", "must be latest-closed-week"),
    )
    for value, message in rejected:
        with pytest.raises(collector.WbAsyncReportError, match=message):
            collector.parse_period(value, NOW)
    with pytest.raises(collector.WbAsyncReportError, match="timezone-aware"):
        collector.parse_period("2026-08-03..2026-08-09", datetime.fromisoformat("2026-08-13T12:00:00"))
    assert collector.parse_args(["--tenant-id", "amirova-test", "--period", "2026-08-03..2026-08-09"]).period == "2026-08-03..2026-08-09"
    assert collector.parse_args(["--tenant-id", "amirova-test"]).period == "latest-closed-week"
