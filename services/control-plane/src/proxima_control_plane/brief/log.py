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
