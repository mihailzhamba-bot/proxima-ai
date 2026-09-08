"""Шаг детектора внутри прогона `brief`: чтение версий -> чистый расчёт (AD-19).

Прогон `brief` зовёт `run_step` только для дня со статусом `ok`; вход прогона
(`collector_run_inputs`) пополняется `input_run_ids` результата - это прогоны
`collect`/`backfill`/`funnel_*`, версии которых детектор прочитал (AD-3). Запись
делает `brief.writer`, отдельного носителя у сигналов нет (AD-9).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import psycopg

from proxima_control_plane.detector import loader
from proxima_control_plane.detector.signals import DetectionResult, detect


def utc_now_iso() -> str:
    """`created_at` сигналов: момент сборки в UTC, без микросекунд (формат date-time контракта)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_step(connection: psycopg.Connection, tenant_id: str, evaluation_day: date, created_at: str) -> DetectionResult:
    facts = loader.read_nm_facts(connection, tenant_id, evaluation_day)
    subjects = loader.read_subjects(connection, tenant_id)
    history = loader.read_funnel_history_days(connection, tenant_id, evaluation_day)
    funnel_rows = loader.read_funnel_window(connection, tenant_id, loader.funnel_eligible(history), evaluation_day)
    return detect(tenant_id, evaluation_day, facts, subjects, history, funnel_rows, created_at)


__all__ = ["run_step", "utc_now_iso"]
