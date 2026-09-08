from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import os
import sys
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
DOWNLOADS_LIST_FIXTURE = ROOT / "services" / "collector" / "tests" / "fixtures" / "wb-api" / "analytics" / "nm_report_downloads" / "sample.json"
PERIOD_FROM = date.fromisoformat("2026-08-03")
PERIOD_TO = date.fromisoformat("2026-08-09")


def archive_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("detail.csv", "nmID,dt,ordersCount\n123,2026-08-03,2\n")
    return output.getvalue()


def new_tenant(connection: psycopg.Connection) -> str:
    tenant_id = f"it-{uuid.uuid4().hex[:12]}"
    connection.execute("INSERT INTO tenants (tenant_id) VALUES (%s)", (tenant_id,))
    return tenant_id


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_real_postgres_preserves_raw_bytes_and_task_idempotency(tmp_path: Path) -> None:
    collector = importlib.import_module("wb_async_report")
    migrations = importlib.import_module("apply_migrations")
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    expected_migrations = sorted(path.name for path in (ROOT / "db" / "migrations").glob("*.sql"))
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        assert migrations.apply_pending(connection) == expected_migrations
        repository = collector.PostgresReportRepository(connection)
        # Story 3.2 (AD-5): the tenant is created by the operator, never by the tool.
        tenant_id = new_tenant(connection)
        run_id = repository.open_run(tenant_id, collector.RUN_KIND)
        period_from = date.fromisoformat("2026-08-03")
        period_to = date.fromisoformat("2026-08-09")
        task, created = repository.reserve_task(tenant_id, period_from, period_to, period_to, run_id)
        assert created is True
        assert task.collector_run_id == run_id
        same_task, created_again = repository.reserve_task(tenant_id, period_from, period_to, period_to, run_id)
        assert created_again is False
        assert same_task.task_id == task.task_id
        repository.mark_initial_create_sent(task.task_id)

        recorder = collector.DurableRawRecorder(tmp_path / "spool", repository)
        malformed = httpx.Response(200, content=b"not-json", headers={"Content-Type": "application/json"})
        recorder.capture(task.task_id, "create", malformed, datetime.fromisoformat("2026-08-13T12:00:00+03:00"))
        with pytest.raises(collector.WbAsyncReportError, match="not valid JSON"):
            collector.json_body(malformed, "create")

        archive = archive_bytes()
        recorder.capture(
            task.task_id,
            "download",
            httpx.Response(200, content=archive, headers={"Content-Type": "application/zip"}),
            datetime.fromisoformat("2026-08-13T12:01:00+03:00"),
        )
        report_rows = collector.parse_report_rows(archive)
        completed = repository.complete_download(
            task.task_id,
            hashlib.sha256(archive).hexdigest(),
            len(archive),
            datetime.fromisoformat("2026-08-13T12:01:00+03:00"),
            report_rows,
        )
        assert completed.parsed_row_count == 1
        assert completed.staged_row_count == 1
        assert completed.collector_run_id == run_id
        completed_again = repository.complete_download(
            task.task_id,
            hashlib.sha256(archive).hexdigest(),
            len(archive),
            datetime.fromisoformat("2026-08-13T12:01:00+03:00"),
            report_rows,
        )
        assert completed_again.staged_row_count == 1
        repository.close_run(run_id, "SUCCEEDED")

        rows = connection.execute(
            "SELECT stage, payload, content_sha256, byte_size FROM raw_wb_analytics_responses WHERE task_id = %s ORDER BY raw_response_id",
            (task.task_id,),
        ).fetchall()
        quota = connection.execute(
            "SELECT count(*) AS count FROM wb_analytics_quota_events WHERE task_id = %s",
            (task.task_id,),
        ).fetchone()
        staged = connection.execute(
            "SELECT row_number, nm_id, row_date, payload FROM stg_wb_nm_report_rows WHERE task_id = %s ORDER BY row_number",
            (task.task_id,),
        ).fetchall()

    assert [dict(row) for row in staged] == [
        {"row_number": 1, "nm_id": 123, "row_date": date.fromisoformat("2026-08-03"), "payload": {"nmID": "123", "dt": "2026-08-03", "ordersCount": "2"}}
    ]
    assert quota is not None and quota["count"] == 1
    assert [row["stage"] for row in rows] == ["create", "download"]
    assert base64.b64decode(rows[0]["payload"]["body_base64"]) == b"not-json"
    reconstructed = base64.b64decode(rows[1]["payload"]["body_base64"])
    assert reconstructed == archive
    assert rows[1]["content_sha256"] == hashlib.sha256(archive).hexdigest()
    assert rows[1]["byte_size"] == len(archive)


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_real_postgres_run_ledger_for_funnel_csv_download() -> None:
    """Story 3.2 against migration 011: no tenant -> error and no row anywhere;
    the run row is RUNNING with kind funnel_csv_download, the task links to it,
    SUCCEEDED/FAILED set finished_at, a second close is an error, and the
    session GUC is the tenant (AD-3, AD-13)."""
    collector = importlib.import_module("wb_async_report")
    migrations = importlib.import_module("apply_migrations")
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        migrations.apply_pending(connection)
        repository = collector.PostgresReportRepository(connection)
        ghost = f"ghost-{uuid.uuid4().hex[:12]}"
        with pytest.raises(collector.WbAsyncReportError, match=f"tenant {ghost} does not exist"):
            repository.open_run(ghost, collector.RUN_KIND)
        with pytest.raises(collector.WbAsyncReportError, match=f"tenant {ghost} does not exist"):
            repository.reserve_task(ghost, PERIOD_FROM, PERIOD_TO, PERIOD_TO, uuid.uuid4())
        for table in ("tenants", "collector_runs", "wb_analytics_report_tasks"):
            count = connection.execute(f"SELECT count(*) AS count FROM {table} WHERE tenant_id = %s", (ghost,)).fetchone()
            assert count is not None and count["count"] == 0, table

        tenant_id = new_tenant(connection)
        repository.bind_tenant(tenant_id)
        guc = connection.execute("SELECT current_setting('proxima.tenant_id', true) AS tenant").fetchone()
        assert guc is not None and guc["tenant"] == tenant_id

        with pytest.raises(collector.WbAsyncReportError, match="invalid collector run kind"):
            repository.open_run(tenant_id, "funnel_csv")
        run_id = repository.open_run(tenant_id, collector.RUN_KIND, git_sha="0902688", image_id="sha256:fixture")
        opened = connection.execute(
            "SELECT tenant_id, kind, status, finished_at, git_sha, image_id FROM collector_runs WHERE run_id = %s", (run_id,)
        ).fetchone()
        assert opened == {"tenant_id": tenant_id, "kind": "funnel_csv_download", "status": "RUNNING", "finished_at": None, "git_sha": "0902688", "image_id": "sha256:fixture"}

        task, created = repository.reserve_task(tenant_id, PERIOD_FROM, PERIOD_TO, PERIOD_TO, run_id)
        assert created is True
        assert task.collector_run_id == run_id
        linked = connection.execute("SELECT collector_run_id FROM wb_analytics_report_tasks WHERE task_id = %s", (task.task_id,)).fetchone()
        assert linked is not None and linked["collector_run_id"] == run_id

        # a second run resuming the unfinished task takes over the audit link
        resuming_run = repository.open_run(tenant_id, collector.RUN_KIND)
        resumed, created_again = repository.reserve_task(tenant_id, PERIOD_FROM, PERIOD_TO, PERIOD_TO, resuming_run)
        assert created_again is False
        assert resumed.task_id == task.task_id
        assert resumed.collector_run_id == resuming_run

        with pytest.raises(collector.WbAsyncReportError, match="invalid collector run status"):
            repository.close_run(run_id, "RUNNING")
        repository.close_run(resuming_run, "FAILED")
        repository.close_run(run_id, "SUCCEEDED")
        with pytest.raises(collector.WbAsyncReportError, match="expected one RUNNING row, updated 0"):
            repository.close_run(run_id, "SUCCEEDED")
        with pytest.raises(collector.WbAsyncReportError, match="expected one RUNNING row, updated 0"):
            repository.close_run(uuid.uuid4(), "FAILED")

        closed = connection.execute(
            "SELECT run_id, status, finished_at IS NOT NULL AS finished FROM collector_runs WHERE tenant_id = %s ORDER BY started_at",
            (tenant_id,),
        ).fetchall()
        assert [(row["run_id"], row["status"], row["finished"]) for row in closed] == [(run_id, "SUCCEEDED", True), (resuming_run, "FAILED", True)]


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_real_postgres_collect_closes_the_run_and_guards_daily_creation(tmp_path: Path) -> None:
    """Whole collect() flow on the real repository with a mocked WB transport:
    a report already created today (fixture list, 30.08.2026) -> no POST,
    task RESERVED, run SUCCEEDED; the next day the same task is created,
    downloaded and staged, the second run SUCCEEDED, a broken download FAILED."""
    collector = importlib.import_module("wb_async_report")
    migrations = importlib.import_module("apply_migrations")
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    fixture_list = DOWNLOADS_LIST_FIXTURE.read_bytes()
    archive = archive_bytes()
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/nm-report/downloads") and "filter[downloadIds]" not in request.url.params:
            return httpx.Response(200, content=fixture_list, headers={"Content-Type": "application/json"})
        if request.method == "POST":
            posts.append(json.loads(request.read())["id"])
            return httpx.Response(200, json={"data": "Created"})
        if "/file/" in request.url.path:
            return httpx.Response(200, content=archive, headers={"Content-Type": "application/zip"})
        return httpx.Response(200, json={"data": [{"id": request.url.params["filter[downloadIds]"], "status": "SUCCESS"}]})

    def run_collect(repository, tenant_id: str, now: datetime, spool: Path, period=(PERIOD_FROM, PERIOD_TO)):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            runner = collector.AsyncReportCollector(
                repository,
                collector.DurableRawRecorder(spool, repository),
                client,
                "header.payload.signature",
                now=lambda: now,
                monotonic=lambda: 0.0,
                sleep=lambda _: None,
                max_wait_seconds=60,
            )
            return runner, runner.collect(tenant_id, *period)
        finally:
            client.close()

    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        migrations.apply_pending(connection)
        repository = collector.PostgresReportRepository(connection)
        tenant_id = new_tenant(connection)
        repository.bind_tenant(tenant_id)

        # Add a Proxima-owned report to the fixture's external-consumer reports -> guard.
        fixture_body = json.loads(fixture_list)
        fixture_body["data"].append({"name": f"proxima-{tenant_id}-period", "createdAt": "2026-08-30 04:17:23"})
        fixture_list = json.dumps(fixture_body).encode()
        guarded_at = datetime.fromisoformat("2026-08-30T06:30:00+03:00")
        runner, guarded = run_collect(repository, tenant_id, guarded_at, tmp_path / "spool-1")
        assert guarded.lifecycle_status == "RESERVED"
        assert posts == []
        assert guarded.collector_run_id == runner.run_id
        first_run = connection.execute("SELECT status, finished_at FROM collector_runs WHERE run_id = %s", (runner.run_id,)).fetchone()
        assert first_run is not None and first_run["status"] == "SUCCEEDED" and first_run["finished_at"] is not None
        captured = connection.execute("SELECT stage FROM raw_wb_analytics_responses WHERE task_id = %s ORDER BY raw_response_id", (guarded.task_id,)).fetchall()
        assert [row["stage"] for row in captured] == ["status"]

        # next day: no report created today -> the RESERVED task is created and downloaded under a new run
        runner, downloaded = run_collect(repository, tenant_id, datetime.fromisoformat("2026-08-31T06:30:00+03:00"), tmp_path / "spool-2")
        assert downloaded.task_id == guarded.task_id
        assert downloaded.lifecycle_status == "DOWNLOADED"
        assert downloaded.collector_run_id == runner.run_id
        assert posts == [str(guarded.task_id)]
        staged = connection.execute("SELECT count(*) AS count FROM stg_wb_nm_report_rows WHERE task_id = %s", (guarded.task_id,)).fetchone()
        assert staged is not None and staged["count"] == 1
        quota = connection.execute("SELECT count(*) AS count FROM wb_analytics_quota_events WHERE task_id = %s", (guarded.task_id,)).fetchone()
        assert quota is not None and quota["count"] == 1

        # a third run finds the task DOWNLOADED: no network, the producer link stays, the run still SUCCEEDED
        runner, again = run_collect(repository, tenant_id, datetime.fromisoformat("2026-09-01T06:30:00+03:00"), tmp_path / "spool-3")
        assert again.lifecycle_status == "DOWNLOADED"
        assert again.collector_run_id == downloaded.collector_run_id != runner.run_id
        assert posts == [str(guarded.task_id)]

        # a failing run (report archive without CSV) is closed FAILED, the task BLOCKED;
        # the handler reads `archive` late, so rebinding it here changes the download
        broken = io.BytesIO()
        with zipfile.ZipFile(broken, "w", zipfile.ZIP_DEFLATED) as bad_archive:
            bad_archive.writestr("detail.txt", "not a csv")
        archive = broken.getvalue()
        other_period = (date.fromisoformat("2026-08-10"), date.fromisoformat("2026-08-16"))
        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            failing = collector.AsyncReportCollector(
                repository,
                collector.DurableRawRecorder(tmp_path / "spool-4", repository),
                client,
                "header.payload.signature",
                now=lambda: datetime.fromisoformat("2026-09-02T06:30:00+03:00"),
                monotonic=lambda: 0.0,
                sleep=lambda _: None,
                max_wait_seconds=60,
            )
            with pytest.raises(collector.WbAsyncReportError, match="exactly one CSV"):
                failing.collect(tenant_id, *other_period)
        finally:
            client.close()
        failed_run = connection.execute("SELECT status, finished_at FROM collector_runs WHERE run_id = %s", (failing.run_id,)).fetchone()
        assert failed_run is not None and failed_run["status"] == "FAILED" and failed_run["finished_at"] is not None
        blocked = connection.execute(
            "SELECT lifecycle_status, collector_run_id FROM wb_analytics_report_tasks WHERE tenant_id = %s AND period_from = %s",
            (tenant_id, other_period[0]),
        ).fetchone()
        assert blocked is not None and blocked["lifecycle_status"] == "BLOCKED" and blocked["collector_run_id"] == failing.run_id

        statuses = connection.execute(
            "SELECT kind, status FROM collector_runs WHERE tenant_id = %s ORDER BY started_at", (tenant_id,)
        ).fetchall()
        assert [(row["kind"], row["status"]) for row in statuses] == [("funnel_csv_download", "SUCCEEDED")] * 3 + [("funnel_csv_download", "FAILED")]
