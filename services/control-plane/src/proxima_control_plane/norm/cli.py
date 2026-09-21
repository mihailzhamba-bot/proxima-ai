"""CLI: python -m proxima_control_plane.norm run --tenant pilot-tenant [--date YYYY-MM-DD].

Один прогон = одна норма на оцениваемый день: медиана окна 14 календарных дней
перед ним по заказам без отмен и по выручке (AD-8). Без `--date` оцениваемым днём
берётся `last_full_day` из `data_status_current` - последний полный день (AD-7).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal

from proxima_control_plane.norm import loader, run_ledger, writer
from proxima_control_plane.norm.log import log_run_event
from proxima_control_plane.norm.median import median, norm_status, norm_window, quantize_money


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _norm_rows(facts: list[loader.DayFact]) -> list[writer.NormRow]:
    """Две метрики по одному окну. Пустая выборка не даёт нормы - это ошибка прогона."""
    if not facts:
        raise ValueError("norm window has no day versions: refusing to invent a norm")
    sample_days = len(facts)
    status = norm_status(sample_days)
    evidence = tuple(sorted({sha for fact in facts for sha in fact.evidence_sha256}))
    orders = quantize_money(median([Decimal(fact.orders_count) for fact in facts]))
    revenue = quantize_money(median([fact.revenue_rub for fact in facts]))
    return [
        writer.NormRow("orders", orders, sample_days, status, evidence),
        writer.NormRow("revenue", revenue, sample_days, status, evidence),
    ]


def _cmd_run(args: argparse.Namespace) -> int:
    tenant_id = loader.validate_tenant(args.tenant)
    connection = loader.connect(tenant_id)
    try:
        evaluation_day = args.date
        if evaluation_day is None:
            evaluation_day = loader.read_last_full_day(connection, tenant_id)
            if evaluation_day is None:
                print("norm: no last_full_day for tenant, nothing to evaluate", file=sys.stderr)
                return 2
        facts = loader.read_window(connection, tenant_id, norm_window(evaluation_day))
        rows = _norm_rows(facts)
        input_run_ids = sorted({fact.run_id for fact in facts})
        run_id = run_ledger.open_run(connection, tenant_id, notes=f"evaluation_day={evaluation_day.isoformat()}")
        try:
            log_run_event("window-read", run_id, tenant_id)
            run_ledger.succeed(
                connection,
                tenant_id,
                run_id,
                lambda conn: writer.write_norm(conn, tenant_id, run_id, evaluation_day, rows, input_run_ids),
            )
        except Exception:
            run_ledger.fail(connection, tenant_id, run_id)
            raise
        sample = rows[0].sample_days
        print(f"norm: evaluation_day={evaluation_day.isoformat()} sample_days={sample}/14 status={rows[0].status}")
        return 0
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m proxima_control_plane.norm")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="compute and materialize the norm for one evaluation day")
    run.add_argument("--tenant", required=True)
    run.add_argument("--date", type=_parse_day, default=None, help="evaluation day; default is last_full_day")
    run.set_defaults(handler=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


__all__ = ["build_parser", "main"]
