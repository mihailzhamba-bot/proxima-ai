"""JSONL audit writer: one line per diagnosis call; write errors never propagate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, entry: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError as exc:
            sys.stderr.write(f"audit write failed ({self.path}): {exc}\n")
