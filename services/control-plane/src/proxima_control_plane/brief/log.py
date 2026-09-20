"""Одна JSON-строка на событие прогона, без payload (AD-17)."""

from __future__ import annotations

import json
import sys

KIND = "brief"


def log_run_event(step: str, run_id: str, tenant_id: str) -> None:
    """Событие шага прогона. Значений метрик и секретов в строке нет по замыслу."""
    line = json.dumps(
        {"kind": KIND, "step": step, "run_id": run_id, "tenant_id": tenant_id},
        ensure_ascii=False,
        sort_keys=True,
    )
    print(line, file=sys.stdout, flush=True)


def log_unknown_subjects(run_id: str, tenant_id: str, nm_ids: tuple[int, ...]) -> None:
    """Одна warn-строка на шаг для всех SKU без текущего предмета (D32)."""
    line = json.dumps(
        {
            "kind": KIND,
            "level": "warn",
            "step": "detector",
            "run_id": run_id,
            "tenant_id": tenant_id,
            "message": "dim_nm_subject_current row is missing; category is UNKNOWN",
            "nm_ids": list(nm_ids),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    print(line, file=sys.stdout, flush=True)
