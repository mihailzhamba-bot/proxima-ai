from __future__ import annotations

import base64
import hashlib
import importlib
import io
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


def archive_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("detail.csv", "nmID,dt,ordersCount\n123,2026-08-03,2\n")
    return output.getvalue()


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_real_postgres_preserves_raw_bytes_and_task_idempotency(tmp_path: Path) -> None:
    collector = importlib.import_module("wb_async_report")
    migrations = importlib.import_module("apply_migrations")
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    expected_migrations = sorted(path.name for path in (ROOT / "db" / "migrations").glob("*.sql"))
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        assert migrations.apply_pending(connection) == expected_migrations
        repository = collector.PostgresReportRepository(connection)
        tenant_id = f"it-{uuid.uuid4().hex[:12]}"
        period_from = date.fromisoformat("2026-08-03")
        period_to = date.fromisoformat("2026-08-09")
        task, created = repository.reserve_task(tenant_id, period_from, period_to, period_to)
        assert created is True
        same_task, created_again = repository.reserve_task(tenant_id, period_from, period_to, period_to)
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
        completed_again = repository.complete_download(
            task.task_id,
            hashlib.sha256(archive).hexdigest(),
            len(archive),
            datetime.fromisoformat("2026-08-13T12:01:00+03:00"),
            report_rows,
        )
        assert completed_again.staged_row_count == 1

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
