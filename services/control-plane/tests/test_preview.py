from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from proxima_control_plane.preview import (
    DayFact,
    DayTotal,
    PreviewError,
    PreviewSnapshot,
    PostgresPreviewReader,
    assert_localhost_host,
    create_preview_app,
)


class StubReader:
    def __init__(self, snapshot: PreviewSnapshot | None) -> None:
        self._snapshot = snapshot

    def latest_snapshot(self, tenant_id: str) -> PreviewSnapshot | None:
        assert tenant_id == "stub-tenant"
        return self._snapshot


def stub_snapshot() -> PreviewSnapshot:
    return PreviewSnapshot(
        tenant_id="stub-tenant",
        run_id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        artifact_sha256="a" * 64,
        release_status="unreleased",
        valid_row_count=3,
        quarantined_row_count=1,
        preview_row_count=2,
        created_at="2026-08-15 12:00:00+03",
        days=(
            DayTotal(
                calendar_day="2026-07-16",
                total_order_count=1,
                products=(DayFact(calendar_day="2026-07-16", nm_id="11051442", order_count=1),),
            ),
            DayTotal(
                calendar_day="2026-07-15",
                total_order_count=5,
                products=(DayFact(calendar_day="2026-07-15", nm_id="11051441", order_count=5),),
            ),
        ),
    )


def client(reader: StubReader) -> TestClient:
    return TestClient(create_preview_app(reader, "stub-tenant"))


def test_preview_page_shows_unreleased_banner_and_day_facts() -> None:
    response = client(StubReader(stub_snapshot())).get("/preview/order-count")
    assert response.status_code == 200
    body = response.text
    assert "UNRELEASED PREVIEW" in body
    assert "not a production release" in body
    assert "a" * 64 in body
    assert "2026-07-15" in body and "2026-07-16" in body
    assert "11051441" in body and "11051442" in body
    assert "total 5" in body


def test_preview_page_returns_404_without_a_succeeded_run() -> None:
    response = client(StubReader(None)).get("/preview/order-count")
    assert response.status_code == 404


def test_preview_route_rejects_all_mutations() -> None:
    preview_client = client(StubReader(stub_snapshot()))
    for method in ("post", "put", "patch", "delete"):
        response = getattr(preview_client, method)("/preview/order-count")
        assert response.status_code == 405, method
    assert preview_client.get("/").status_code == 404
    assert preview_client.get("/preview/order-count/extra").status_code == 404


def test_preview_host_guard_accepts_only_loopback() -> None:
    for host in ("127.0.0.1", "localhost", "::1"):
        assert_localhost_host(host)
    for host in ("0.0.0.0", "192.168.1.5", "", "example.local"):
        with pytest.raises(PreviewError) as error:
            assert_localhost_host(host)
        assert error.value.code == "HOST_NOT_LOOPBACK"


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_postgres_reader_builds_latest_snapshot() -> None:
    import psycopg
    from psycopg.rows import dict_row

    tenant = "preview-reader-test"
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        for statement in (
            "DELETE FROM preview_order_counts WHERE tenant_id = %(tenant)s",
            "DELETE FROM preview_quarantine_rows WHERE task_id IN (SELECT task_id FROM wb_analytics_report_tasks WHERE tenant_id = %(tenant)s)",
            "DELETE FROM artifact_parse_runs WHERE tenant_id = %(tenant)s",
            "DELETE FROM stg_wb_nm_report_rows WHERE task_id IN (SELECT task_id FROM wb_analytics_report_tasks WHERE tenant_id = %(tenant)s)",
            "DELETE FROM wb_analytics_report_tasks WHERE tenant_id = %(tenant)s",
            "DELETE FROM tenants WHERE tenant_id = %(tenant)s",
        ):
            connection.execute(statement, {"tenant": tenant})
        connection.execute("INSERT INTO tenants (tenant_id) VALUES (%(tenant)s)", {"tenant": tenant})
        task_id = uuid.uuid4()
        run_id = uuid.uuid4()
        artifact_sha = "b" * 64
        connection.execute(
            """
            INSERT INTO wb_analytics_report_tasks
            (task_id, tenant_id, report_type, period_from, period_to, timezone, aggregation_level,
             request_body, lifecycle_status, api_status, downloaded_sha256, downloaded_size, downloaded_at,
             parsed_row_count, staged_row_count)
            VALUES (%(task)s::uuid, %(tenant)s, 'DETAIL_HISTORY_REPORT', '2026-07-14', '2026-08-14',
                    'Europe/Moscow', 'day',
                    jsonb_build_object('id', %(task)s::uuid::text, 'reportType', 'DETAIL_HISTORY_REPORT'),
                    'DOWNLOADED', 'SUCCESS', %(sha)s, 1234, CURRENT_TIMESTAMP, 3, 3)
            """,
            {"task": task_id, "tenant": tenant, "sha": artifact_sha},
        )
        connection.execute(
            """
            INSERT INTO artifact_parse_runs
            (run_id, tenant_id, task_id, profile, artifact_sha256, lifecycle_status,
             staged_row_count, valid_row_count, quarantined_row_count, preview_row_count, completed_at)
            VALUES (%(run)s::uuid, %(tenant)s, %(task)s::uuid, 'wb_detail_history_v1', %(sha)s, 'SUCCEEDED',
                    3, 2, 1, 2, CURRENT_TIMESTAMP)
            """,
            {"run": run_id, "tenant": tenant, "task": task_id, "sha": artifact_sha},
        )
        for day, nm_id, count in (("2026-07-15", 11051441, 5), ("2026-07-16", 11051442, 1)):
            connection.execute(
                """
                INSERT INTO preview_order_counts (tenant_id, task_id, run_id, calendar_day, nm_id, order_count)
                VALUES (%(tenant)s, %(task)s::uuid, %(run)s::uuid, %(day)s::date, %(nm)s, %(count)s)
                """,
                {"tenant": tenant, "task": task_id, "run": run_id, "day": day, "nm": nm_id, "count": count},
            )

    snapshot = PostgresPreviewReader(dsn).latest_snapshot(tenant)
    assert snapshot is not None
    assert snapshot.artifact_sha256 == "b" * 64
    assert snapshot.release_status == "unreleased"
    assert [day.calendar_day for day in snapshot.days] == ["2026-07-16", "2026-07-15"]
    assert snapshot.days[0].total_order_count == 1
    assert snapshot.days[1].total_order_count == 5

    html_client = TestClient(create_preview_app(PostgresPreviewReader(dsn), tenant))
    response = html_client.get("/preview/order-count")
    assert response.status_code == 200
    assert "UNRELEASED PREVIEW" in response.text
