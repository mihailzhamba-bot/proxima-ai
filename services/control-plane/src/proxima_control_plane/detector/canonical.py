"""Канонический хэш входа и результата: детерминизм прогона проверяется, а не постулируется.

`_encode`/`canonical_hash` перенесены из ветки `pmm-20-scn-001` (D32). Отличие одно:
Decimal кодируется своим точным текстом (`str`), без `normalize()` - нормализация
денег не переносится, деньги в payload уже строки с двумя знаками (AD-10), а вход
из `numeric(14,2)` приходит в одной форме.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping


def _encode(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _encode(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Mapping):
        return {str(k): _encode(v) for k, v in obj.items()}
    if isinstance(obj, (set, frozenset)):
        items = [_encode(item) for item in obj]
        items.sort(key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return items
    if isinstance(obj, (list, tuple)):
        return [_encode(item) for item in obj]
    raise TypeError(f"cannot canonically encode {type(obj).__name__}")


def canonical_hash(obj: Any) -> str:
    payload = json.dumps(_encode(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["canonical_hash"]
