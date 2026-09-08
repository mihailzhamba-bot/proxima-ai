"""CLI: python -m proxima_control_plane.detector evaluate --tenant amirova-test [--date YYYY-MM-DD].

Сухой прогон детектора: читает версии `_current` под ролью norm и печатает
сигналы JSON в stdout. В реестр прогонов ничего не пишет - боевой путь сигналов
один: шаг прогона `brief` (AD-19), где `signals[]` зависят от `brief.status`.
Здесь статус сводки не проверяется, поэтому вывод - материал для сверки
(harness, теневой пересчёт), а не сводка.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from proxima_control_plane.brief import loader as brief_loader
from proxima_control_plane.detector.step import run_step, utc_now_iso


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _cmd_evaluate(args: argparse.Namespace) -> int:
    tenant_id = brief_loader.validate_tenant(args.tenant)
    connection = brief_loader.connect(tenant_id)
    try:
        evaluation_day = args.date
        if evaluation_day is None:
            status = brief_loader.read_data_status(connection, tenant_id)
            if status is None or status.last_full_day is None:
                print("detector: no data_status row for tenant, nothing to evaluate", file=sys.stderr)
                return 2
            evaluation_day = status.last_full_day
        result = run_step(connection, tenant_id, evaluation_day, created_at=utc_now_iso())
    finally:
        connection.close()
    document = {
        "evaluation_day": result.evaluation_day.isoformat(),
        "snapshot_id": result.snapshot_id,
        "counters": result.counters(),
        "signals": list(result.signals),
    }
    print(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m proxima_control_plane.detector")
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate", help="dry-run: print SCN-001 signals for one day without writing")
    evaluate.add_argument("--tenant", required=True)
    evaluate.add_argument("--date", type=_parse_day, default=None, help="evaluation day; default is last_full_day")
    evaluate.set_defaults(handler=_cmd_evaluate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


__all__ = ["build_parser", "main"]
