from __future__ import annotations

import re
from pathlib import Path


def test_database_sql_does_not_use_current_date() -> None:
    root = Path(__file__).resolve().parents[2] / "db"
    offenders = [path for path in root.rglob("*.sql") if re.search(r"\bCURRENT_DATE\b", path.read_text(), re.IGNORECASE)]
    assert offenders == [], f"CURRENT_DATE is forbidden in db SQL: {offenders}"
