from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment
from psycopg.rows import dict_row


class PreviewError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DayFact:
    calendar_day: str
    nm_id: str
    order_count: int


@dataclass(frozen=True)
class DayTotal:
    calendar_day: str
    total_order_count: int
    products: tuple[DayFact, ...]


@dataclass(frozen=True)
class PreviewSnapshot:
    tenant_id: str
    run_id: str
    task_id: str
    artifact_sha256: str
    release_status: str
    valid_row_count: int
    quarantined_row_count: int
    preview_row_count: int
    created_at: str
    days: tuple[DayTotal, ...]


class PreviewReader(Protocol):
    def latest_snapshot(self, tenant_id: str) -> PreviewSnapshot | None: ...


class PostgresPreviewReader:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def latest_snapshot(self, tenant_id: str) -> PreviewSnapshot | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as connection:
            run = connection.execute(
                """
                SELECT r.run_id::text AS run_id, r.task_id::text AS task_id, r.tenant_id,
                       r.artifact_sha256, r.valid_row_count, r.quarantined_row_count,
                       r.preview_row_count, r.created_at::text AS created_at
                FROM artifact_parse_runs r
                WHERE r.tenant_id = %s AND r.profile = 'wb_detail_history_v1' AND r.lifecycle_status = 'SUCCEEDED'
                ORDER BY r.created_at DESC
                LIMIT 1
                """,
                (tenant_id,),
            ).fetchone()
            if run is None:
                return None
            rows = connection.execute(
                """
                SELECT calendar_day::text AS calendar_day, nm_id::text AS nm_id, order_count
                FROM preview_order_counts
                WHERE run_id = %s::uuid
                ORDER BY calendar_day DESC, order_count DESC, nm_id
                """,
                (run["run_id"],),
            ).fetchall()
        grouped: dict[str, list[DayFact]] = {}
        for row in rows:
            grouped.setdefault(row["calendar_day"], []).append(
                DayFact(calendar_day=row["calendar_day"], nm_id=row["nm_id"], order_count=int(row["order_count"]))
            )
        days = tuple(
            DayTotal(
                calendar_day=day,
                total_order_count=sum(fact.order_count for fact in facts),
                products=tuple(facts),
            )
            for day, facts in sorted(grouped.items(), reverse=True)
        )
        return PreviewSnapshot(
            tenant_id=run["tenant_id"],
            run_id=run["run_id"],
            task_id=run["task_id"],
            artifact_sha256=run["artifact_sha256"],
            release_status="unreleased",
            valid_row_count=int(run["valid_row_count"]),
            quarantined_row_count=int(run["quarantined_row_count"]),
            preview_row_count=int(run["preview_row_count"]),
            created_at=run["created_at"],
            days=days,
        )


TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<title>PROXIMA AI - preview order_count (unreleased)</title>
<style>
  body { font-family: ui-monospace, monospace; margin: 2rem; color: #111; background: #fafafa; }
  .banner { background: #b45309; color: #fff; padding: 0.5rem 1rem; font-weight: bold; display: inline-block; }
  .lineage { margin: 1rem 0; font-size: 0.85rem; color: #444; white-space: pre-wrap; }
  table { border-collapse: collapse; margin-top: 0.5rem; }
  th, td { border: 1px solid #ccc; padding: 0.35rem 0.75rem; text-align: left; }
  th { background: #eee; }
  .day { margin-top: 1.5rem; }
  .muted { color: #666; }
</style>
</head>
<body>
<p class="banner">UNRELEASED PREVIEW - not a production release</p>
<div class="lineage">tenant: {{ snapshot.tenant_id }}
run: {{ snapshot.run_id }}
task: {{ snapshot.task_id }}
artifact sha256: {{ snapshot.artifact_sha256 }}
rows: {{ snapshot.valid_row_count }} valid / {{ snapshot.quarantined_row_count }} quarantined / {{ snapshot.preview_row_count }} preview facts
created: {{ snapshot.created_at }} (Europe/Moscow)</div>
{% if snapshot.days %}
<h2>Daily order_count by calendar day</h2>
{% for day in snapshot.days %}
<div class="day">
<h3>{{ day.calendar_day }} - total {{ day.total_order_count }}</h3>
<table>
<tr><th>nmId</th><th>order_count</th></tr>
{% for fact in day.products %}
<tr><td>{{ fact.nm_id }}</td><td>{{ fact.order_count }}</td></tr>
{% endfor %}
</table>
</div>
{% endfor %}
{% else %}
<p>No preview facts found for this tenant.</p>
{% endif %}
<p class="muted">Read-only localhost preview. No writes, no raw payloads, no production release status.</p>
</body>
</html>
"""


def create_preview_app(reader: PreviewReader, tenant_id: str) -> FastAPI:
    environment = Environment(autoescape=True)
    template = environment.from_string(TEMPLATE)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/preview/order-count", response_class=HTMLResponse)
    def order_count_preview() -> HTMLResponse:
        snapshot = reader.latest_snapshot(tenant_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="no succeeded preview run for tenant")
        return HTMLResponse(template.render(snapshot=snapshot))

    return app


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def assert_localhost_host(host: str) -> None:
    if host not in LOOPBACK_HOSTS:
        raise PreviewError("HOST_NOT_LOOPBACK", f"preview host must be loopback, got {host!r}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="proxima-preview", description="localhost-only unreleased order_count preview")
    parser.add_argument("--dsn-file", required=True, help="private file (mode 0600) with the PostgreSQL DSN")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args(argv)

    assert_localhost_host(args.host)

    import os
    import stat

    dsn_stat = os.stat(args.dsn_file)
    if stat.S_IMODE(dsn_stat.st_mode) & 0o077:
        raise PreviewError("DSN_FILE_UNSAFE", "DSN file must be a private file with mode 0600")
    dsn = open(args.dsn_file, encoding="utf-8").read().strip()
    if not dsn:
        raise PreviewError("DSN_FILE_INVALID", "DSN file is empty")

    import uvicorn

    app = create_preview_app(PostgresPreviewReader(dsn), args.tenant)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
