"""SCN-001 smoke (R16): read-only check of the payload column registry against staging.

Prints a comparison of COLUMN_MAP keys versus one real payload row fetched through
the tunnel. Without DATABASE_URI (or with the tunnel down) prints UNKNOWN and
exits 0. Not part of `make verify`.
"""

from __future__ import annotations

import sys
from typing import Any, Mapping

from proxima_control_plane.detectors.scn001.loader import COLUMN_MAP, DbExecutor, db_from_env

SMOKE_ROW_SQL = """
SELECT t.task_id::text AS task_id,
       r.row_number,
       r.payload
FROM wb_analytics_report_tasks AS t
JOIN stg_wb_nm_report_rows AS r ON r.task_id = t.task_id
WHERE t.lifecycle_status = 'DOWNLOADED'
ORDER BY t.downloaded_at DESC NULLS LAST, t.task_id DESC, r.row_number
LIMIT 1
"""


def _fetch_smoke_row(db: DbExecutor) -> tuple[str, int, Mapping[str, Any]]:
    cursor = db.execute(SMOKE_ROW_SQL)
    rows = cursor.fetchall()
    if not rows:
        raise LookupError("no DOWNLOADED staging rows yet")
    task_id, row_number, payload = rows[0]
    return str(task_id), int(row_number), payload


def main(uri: str | None = None, stream: Any = None) -> int:
    out = stream if stream is not None else sys.stdout
    print("SMOKE R16: payload column registry vs real staging row (read-only, one row)", file=out)
    try:
        db = db_from_env(uri)
    except Exception as exc:
        print(f"SMOKE R16: UNKNOWN ({type(exc).__name__})", file=out)
        return 0
    try:
        task_id, row_number, payload = _fetch_smoke_row(db)
    except Exception as exc:
        print(f"SMOKE R16: UNKNOWN ({type(exc).__name__})", file=out)
        return 0
    finally:
        close = getattr(db, "close", None)
        if callable(close):
            close()
    print(f"row: task_id={task_id} row_number={row_number}", file=out)
    registry_columns = set(COLUMN_MAP.values())
    missing: list[str] = []
    for field, column in COLUMN_MAP.items():
        if column in payload:
            print(f"  field={field:<14} column={column!r:<16} PRESENT type={type(payload[column]).__name__}", file=out)
        else:
            missing.append(column)
            print(f"  field={field:<14} column={column!r:<16} MISSING", file=out)
    extra = sorted(str(k) for k in payload if k not in registry_columns)
    print(f"payload keys not in registry: {extra if extra else 'none'}", file=out)
    status = "OK" if not missing else f"MISMATCH (missing: {', '.join(missing)})"
    print(f"SMOKE R16: REGISTRY STATUS {status}", file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
