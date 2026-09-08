"""CLI: python -m proxima_control_plane.brief run --tenant amirova-test [--date YYYY-MM-DD].

Один прогон = одна сводка на день (AD-9). Без `--date` днём сводки берётся
`last_full_day` из `data_status_current` - последний полный день (AD-7); норма
читается за тот же день из `norm_daily_current` (AD-8). Прогон, работа и
`SUCCEEDED` идут по контракту реестра прогонов (AD-3). Детектор SCN-001 -
шаг этого же прогона (AD-19, Story 4.1): только для дня `ok` он читает версии
по nmId и кладёт `signals[]` в payload, а прочитанные прогоны - в `run_inputs`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal

from proxima_control_plane.brief import assembler, loader, run_ledger, writer
from proxima_control_plane.brief.log import log_run_event
from proxima_control_plane.detector.step import run_step as run_detector_step, utc_now_iso


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _cmd_run(args: argparse.Namespace) -> int:
    tenant_id = loader.validate_tenant(args.tenant)
    connection = loader.connect(tenant_id)
    try:
        brief_day = args.date
        if brief_day is None:
            status = loader.read_data_status(connection, tenant_id)
            if status is None or status.last_full_day is None:
                print("brief: no data_status row for tenant, nothing to brief", file=sys.stderr)
                return 2
            brief_day = status.last_full_day
        norms = loader.read_norms(connection, tenant_id, brief_day)
        actual = loader.read_actual(connection, tenant_id, brief_day)
        data_status = loader.read_data_status(connection, tenant_id)
        fact_run_ids = loader.read_fact_run_ids(connection, tenant_id, brief_day)
        norm_run_ids = loader.read_norm_input_run_ids(connection, tenant_id, brief_day)
        input_run_ids = sorted(set(fact_run_ids) | set(norm_run_ids))
        # Прогон открывается до сборки, а не после: если сборка упадёт - например,
        # норма законно равна нулю и отклонение не определено - попытка обязана
        # остаться в реестре как FAILED, а не исчезнуть вместе с трейсбеком (AD-3).
        run_id = run_ledger.open_run(connection, tenant_id, notes=f"brief_day={brief_day.isoformat()}")
        signals_note = ""
        try:
            day = assembler.build_day(brief_day, norms, actual, data_status, fact_run_ids)
            if day.status == "ok" and not input_run_ids:
                raise ValueError("brief payload without inputs: refusing to write a source-free summary")
            log_run_event("inputs-read", run_id, tenant_id)
            if day.status == "ok":
                # Детектор - шаг прогона сводки (AD-19): сигналы только при `ok`,
                # при `insufficient`/`blocked` он даже не читает факты (PRD FR-7).
                detection = run_detector_step(connection, tenant_id, brief_day, created_at=utc_now_iso())
                day = assembler.with_signals(day, detection.signals)
                input_run_ids = sorted(set(input_run_ids) | set(detection.input_run_ids))
                counters = detection.counters()
                signals_note = (
                    f", signals {counters['signals']} (sku {counters['sku_total']}, insufficient {counters['sku_insufficient']})"
                )
                log_run_event("detector", run_id, tenant_id)
            run_ledger.succeed(
                connection,
                tenant_id,
                run_id,
                lambda conn: writer.write_brief(
                    conn,
                    tenant_id,
                    run_id,
                    writer.BriefRow(brief_day=day.brief_day, status=day.status, payload=day.payload),
                    input_run_ids,
                ),
            )
        except Exception:
            run_ledger.fail(connection, tenant_id, run_id)
            raise
        actual_note = ""
        if day.status == "ok":
            orders = day.payload["actual"]["orders"]
            norm_orders = day.payload["norm"]["orders"]
            deviation = day.payload["deviation_pct"]["orders"]
            actual_note = f", orders {orders} vs norm {norm_orders} ({deviation}%)"
        print(f"brief: brief_day={brief_day.isoformat()} status={day.status}{actual_note}{signals_note}")
        return 0
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m proxima_control_plane.brief")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="build and materialize the brief for one day")
    run.add_argument("--tenant", required=True)
    run.add_argument("--date", type=_parse_day, default=None, help="brief day; default is last_full_day")
    run.set_defaults(handler=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


__all__ = ["build_parser", "main"]
