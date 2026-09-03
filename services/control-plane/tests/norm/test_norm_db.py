"""DB-тест нормы: окно, статусы, версии по прогону (AD-3, AD-8, AD-13).

Запускается только из `tools/pg_local_roundtrip.sh`, где поднят одноразовый
PostgreSQL 16 и экспортированы DSN ролей. Без них тест самопропускается, поэтому
обычный `make test` его не гоняет.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import psycopg
import pytest

from proxima_control_plane.norm.cli import main

OWNER_DSN = os.environ.get("PROXIMA_TEST_POSTGRES_DSN", "")
NORM_DSN = os.environ.get("PROXIMA_TEST_DSN_NORM", "")
TENANT = "amirova-test"
EVALUATION_DAY = date(2026, 8, 29)
# Заказы окна: два средних значения 34 и 35, поэтому норма = 34.5 (D27).
ORDERS = (28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41)
# Выручка: ряд с шагом 2 вокруг базы так, что два средних значения окна -
# base-1 и base+1, поэтому медиана равна базе точно (проверка D27 на деньгах).
REVENUE_BASE = Decimal("34595.00")

pytestmark = pytest.mark.skipif(
    not (OWNER_DSN and NORM_DSN),
    reason="PROXIMA_TEST_POSTGRES_DSN and PROXIMA_TEST_DSN_NORM must be set (run via tools/pg_local_roundtrip.sh)",
)


def _revenue(offset: int) -> Decimal:
    """Ряд вокруг базы: у 14 точек средние - индексы 6 и 7, то есть base-1 и base+1."""
    return REVENUE_BASE + (Decimal(offset) - Decimal("6.5")) * Decimal(2)


@pytest.fixture
def seeded() -> str:
    """Сеет 14 версий дней окна owner-соединением и убирает свои прогоны после."""
    seed_run = str(uuid.uuid4())
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        owner.execute("INSERT INTO tenants (tenant_id) VALUES (%s) ON CONFLICT DO NOTHING", (TENANT,))
        owner.execute(
            """
            INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at)
            VALUES (%s, %s, 'collect', 'SUCCEEDED', CURRENT_TIMESTAMP)
            """,
            (seed_run, TENANT),
        )
        for offset, orders in enumerate(ORDERS):
            day = EVALUATION_DAY - timedelta(days=14 - offset)
            owner.execute(
                """
                INSERT INTO fact_cabinet_daily
                    (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count,
                     returns_count, revenue_rub, forpay_rub, evidence_sha256)
                VALUES (%s, %s, %s, %s, 0, %s, 0, %s, %s, %s)
                """,
                (TENANT, day, seed_run, orders, orders, _revenue(offset), _revenue(offset), [f"{offset:064x}"]),
            )
    yield seed_run
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        # Порядок обязателен: collector_run_inputs.input_run_id ссылается на
        # collector_runs без каскада, поэтому зависимые прогоны нормы уходят
        # первыми, а входной collect - только после них (то же замыкание, что
        # делает tools/delete_run.py по AD-3).
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'norm'", (TENANT,))
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'collect'", (TENANT,))


def _norm_rows(connection: psycopg.Connection) -> dict[str, tuple[Decimal, int, str]]:
    rows = connection.execute(
        """
        SELECT metric, value, sample_days, status
        FROM norm_daily_current
        WHERE tenant_id = %s AND evaluation_day = %s
        """,
        (TENANT, EVALUATION_DAY),
    ).fetchall()
    return {row[0]: (row[1], row[2], row[3]) for row in rows}


def _run() -> int:
    return main(["run", "--tenant", TENANT, "--date", EVALUATION_DAY.isoformat()])


def test_full_window_gives_ok_and_the_expected_medians(seeded: str) -> None:
    assert _run() == 0
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        rows = _norm_rows(connection)
        assert rows["orders"] == (Decimal("34.50"), 14, "ok")
        assert rows["revenue"] == (REVENUE_BASE, 14, "ok")
        run_row = connection.execute(
            "SELECT kind, status FROM collector_runs WHERE tenant_id = %s AND kind = 'norm'",
            (TENANT,),
        ).fetchone()
        assert run_row == ("norm", "SUCCEEDED")
        inputs = connection.execute(
            """
            SELECT count(*) FROM collector_run_inputs i
            JOIN collector_runs r ON r.run_id = i.run_id
            WHERE i.tenant_id = %s AND r.kind = 'norm'
            """,
            (TENANT,),
        ).fetchone()
        assert inputs[0] == 1


def test_five_missing_days_give_nine_of_fourteen_and_insufficient(seeded: str) -> None:
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        for offset in range(5):
            day = EVALUATION_DAY - timedelta(days=14 - offset)
            owner.execute(
                "DELETE FROM fact_cabinet_daily WHERE tenant_id = %s AND calendar_day = %s",
                (TENANT, day),
            )
    assert _run() == 0
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        rows = _norm_rows(connection)
        assert rows["orders"][1] == 9
        assert rows["orders"][2] == "insufficient"
        assert rows["revenue"][1] == 9
        assert rows["revenue"][2] == "insufficient"


def test_a_second_run_adds_a_version_and_current_returns_the_latest(seeded: str) -> None:
    assert _run() == 0
    assert _run() == 0
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        versions = connection.execute(
            "SELECT count(DISTINCT run_id) FROM norm_daily WHERE tenant_id = %s AND evaluation_day = %s",
            (TENANT, EVALUATION_DAY),
        ).fetchone()
        assert versions[0] == 2
        current = connection.execute(
            "SELECT count(*) FROM norm_daily_current WHERE tenant_id = %s AND evaluation_day = %s",
            (TENANT, EVALUATION_DAY),
        ).fetchone()
        assert current[0] == 2  # ровно одна строка на метрику


def test_norm_role_cannot_write_facts_it_only_reads(seeded: str) -> None:
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                """
                INSERT INTO fact_cabinet_daily
                    (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count,
                     returns_count, revenue_rub, forpay_rub, evidence_sha256)
                VALUES (%s, %s, %s, 1, 0, 0, 0, 0, 0, %s)
                """,
                (TENANT, EVALUATION_DAY, seeded, ["0" * 64]),
            )
