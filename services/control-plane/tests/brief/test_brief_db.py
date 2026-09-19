"""DB-тест сводки: статусы, payload, run_inputs, brief_current, RLS (AD-3, AD-9, AD-13).

Запускается только из `tools/pg_local_roundtrip.sh`, где поднят одноразовый
PostgreSQL 16, применены миграции, разданы роли и экспортированы DSN. Без них
тест самопропускается, поэтому обычный `make test` его не гоняет.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import psycopg
import pytest

from proxima_control_plane.brief.cli import main as brief_main
from proxima_control_plane.norm.cli import main as norm_main

OWNER_DSN = os.environ.get("PROXIMA_TEST_POSTGRES_DSN", "")
NORM_DSN = os.environ.get("PROXIMA_TEST_DSN_NORM", "")
WEBAPP_DSN = os.environ.get("PROXIMA_TEST_DSN_WEBAPP", "")
TENANT = "amirova-test"
# «Вчера» по календарю Europe/Moscow (AD-7): тогда data_status_current честно
# свежий (stale = false) относительно часов кластера, без подделки времени.
BRIEF_DAY = datetime.now(ZoneInfo("Europe/Moscow")).date() - timedelta(days=1)
# Заказы окна: два средних значения 34 и 35, поэтому норма = 34.5 (D27).
ORDERS = (28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41)
REVENUE_BASE = Decimal("34595.00")
ACTUAL_ORDERS = 27
ACTUAL_REVENUE = Decimal("41141.00")

pytestmark = pytest.mark.skipif(
    not (OWNER_DSN and NORM_DSN and WEBAPP_DSN),
    reason=(
        "PROXIMA_TEST_POSTGRES_DSN, PROXIMA_TEST_DSN_NORM and PROXIMA_TEST_DSN_WEBAPP "
        "must be set (run via tools/pg_local_roundtrip.sh)"
    ),
)


def _revenue(offset: int) -> Decimal:
    """Ряд вокруг базы: у 14 точек средние - индексы 6 и 7, то есть base-1 и base+1."""
    return REVENUE_BASE + (Decimal(offset) - Decimal("6.5")) * Decimal(2)


@pytest.fixture
def seeded() -> str:
    """Сеет окно нормы и день сводки owner-соединением; снимает свои прогоны после."""
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
        for offset in range(14):
            day = BRIEF_DAY - timedelta(days=14 - offset)
            orders = ORDERS[offset]
            revenue = _revenue(offset)
            owner.execute(
                """
                INSERT INTO fact_cabinet_daily
                    (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count,
                     returns_count, revenue_rub, forpay_rub, evidence_sha256)
                VALUES (%s, %s, %s, %s, 0, %s, 0, %s, %s, %s)
                """,
                (TENANT, day, seed_run, orders, orders, revenue, revenue, [f"{offset:064x}"]),
            )
        # Сам день сводки: окно нормы его не захватывает (AD-8), а факту на
        # brief_day быть - это «вчера» из истории пользователя.
        owner.execute(
            """
            INSERT INTO fact_cabinet_daily
                (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count,
                 returns_count, revenue_rub, forpay_rub, evidence_sha256)
            VALUES (%s, %s, %s, %s, 0, %s, 0, %s, %s, %s)
            """,
            (TENANT, BRIEF_DAY, seed_run, ACTUAL_ORDERS, ACTUAL_ORDERS, ACTUAL_REVENUE, ACTUAL_REVENUE, ["ff" * 32]),
        )
    yield seed_run
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        # collector_run_inputs -> collector_runs, norm_daily/brief_daily -> collector_runs:
        # сначала зависимые прогоны, затем входной collect (замыкание tools/delete_run.py).
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'brief'", (TENANT,))
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'norm'", (TENANT,))
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'collect'", (TENANT,))


def _norm_and_brief() -> None:
    assert norm_main(["run", "--tenant", TENANT, "--date", BRIEF_DAY.isoformat()]) == 0
    assert brief_main(["run", "--tenant", TENANT, "--date", BRIEF_DAY.isoformat()]) == 0


def _payload_with_status(connection: psycopg.Connection) -> dict:
    row = connection.execute(
        """
        SELECT status, payload
        FROM brief_daily
        WHERE tenant_id = %s AND brief_day = %s
        """,
        (TENANT, BRIEF_DAY),
    ).fetchone()
    assert row is not None, "brief_daily row is missing"
    return {"status": row[0], "payload": row[1]}


def test_ok_day_writes_a_contract_payload_with_expected_deviations(seeded: str) -> None:
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        result = _payload_with_status(connection)
    assert result["status"] == "ok"
    payload = result["payload"]
    assert payload["schema_version"] == 1
    assert payload["evaluation_day"] == BRIEF_DAY.isoformat()
    assert payload["actual"] == {"orders": ACTUAL_ORDERS, "revenue": "41141.00"}
    assert payload["norm"] == {
        "orders": "34.50",
        "revenue": "34595.00",
        "window_days": 14,
        "sample_days": 14,
    }
    assert payload["deviation_pct"] == {"orders": -21.7, "revenue": 18.9}
    assert payload["threshold"] == {"value": -30, "source": "docs/exec-plans/active/loop-pilot.txt: план Mike 2026-09-13, порог пилота", "date": "2026-09-13"}  # LOOP pilot: approved provisional threshold, Mike 2026-09-13
    assert payload["signals"] == []
    assert payload["source_refs"]
    # data_status скопирован из view на момент записи (AD-9): collect был только что.
    assert payload["data_status"]["stale"] is False
    assert payload["data_status"]["last_full_day"] == BRIEF_DAY.isoformat()


def test_run_inputs_record_the_fact_and_norm_runs(seeded: str) -> None:
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        inputs = connection.execute(
            """
            SELECT count(*), count(DISTINCT r.kind)
            FROM collector_run_inputs i
            JOIN collector_runs r ON r.run_id = i.run_id
            WHERE i.tenant_id = %s AND r.kind = 'brief'
            """,
            (TENANT,),
        ).fetchone()
        assert inputs[0] >= 2  # входной collect и прогон нормы
        kinds = connection.execute(
            """
            SELECT DISTINCT r2.kind
            FROM collector_run_inputs i
            JOIN collector_runs r ON r.run_id = i.run_id
            JOIN collector_runs r2 ON r2.run_id = i.input_run_id
            WHERE i.tenant_id = %s AND r.kind = 'brief'
            """,
            (TENANT,),
        ).fetchall()
        assert {row[0] for row in kinds} == {"collect", "norm"}


def test_brief_current_holds_exactly_one_row_per_tenant(seeded: str) -> None:
    _norm_and_brief()
    _norm_and_brief()  # второй прогон добавляет версию, current оставляет одну строку
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        current = connection.execute(
            "SELECT count(*) FROM brief_current WHERE tenant_id = %s", (TENANT,)
        ).fetchone()
        assert current[0] == 1
        versions = connection.execute(
            "SELECT count(*) FROM brief_daily WHERE tenant_id = %s AND brief_day = %s",
            (TENANT, BRIEF_DAY),
        ).fetchone()
        assert versions[0] == 2


def test_insufficient_norm_status_copies_into_brief_status(seeded: str) -> None:
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        # Окно теряет пять дней: 9/14 -> норма insufficient (AD-8).
        for offset in range(5):
            day = BRIEF_DAY - timedelta(days=14 - offset)
            owner.execute(
                "DELETE FROM fact_cabinet_daily WHERE tenant_id = %s AND calendar_day = %s",
                (TENANT, day),
            )
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        result = _payload_with_status(connection)
    assert result["status"] == "insufficient"
    # Форма payload не зависит от статуса (D30): норма отдаётся как есть,
    # отклонение против неполного окна числом не называется.
    assert result["payload"]["norm"]["sample_days"] == 9
    assert result["payload"]["deviation_pct"] is None
    assert result["payload"]["actual"]["orders"] == ACTUAL_ORDERS
    assert result["payload"]["threshold"] == {"value": -30, "source": "docs/exec-plans/active/loop-pilot.txt: план Mike 2026-09-13, порог пилота", "date": "2026-09-13"}
    assert result["payload"]["signals"] == []


def test_missing_norm_versions_block_the_day(seeded: str) -> None:
    assert brief_main(["run", "--tenant", TENANT, "--date", BRIEF_DAY.isoformat()]) == 0
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        result = _payload_with_status(connection)
    assert result["status"] == "blocked"
    # Отсутствие записано явно, а не пропущенным ключом (D30).
    assert result["payload"]["norm"] is None
    assert result["payload"]["deviation_pct"] is None
    assert result["payload"]["reason"]
    assert result["payload"]["threshold"] == {"value": -30, "source": "docs/exec-plans/active/loop-pilot.txt: план Mike 2026-09-13, порог пилота", "date": "2026-09-13"}
    assert result["payload"]["signals"] == []


def test_webapp_role_sees_brief_current_only_with_tenant_guc(seeded: str) -> None:
    _norm_and_brief()
    with psycopg.connect(WEBAPP_DSN, autocommit=True) as connection:
        without_guc = connection.execute(
            "SELECT count(*) FROM brief_current WHERE tenant_id = %s", (TENANT,)
        ).fetchone()
        assert without_guc[0] == 0  # RLS без GUC не отдаёт ни строки (AD-12)
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        with_guc = connection.execute(
            "SELECT count(*) FROM brief_current WHERE tenant_id = %s", (TENANT,)
        ).fetchone()
        assert with_guc[0] == 1
        row = connection.execute(
            """
            SELECT status, payload->>'evaluation_day'
            FROM brief_current WHERE tenant_id = %s
            """,
            (TENANT,),
        ).fetchone()
        assert row == ("ok", BRIEF_DAY.isoformat())


def test_brief_role_cannot_write_norm_or_facts(seeded: str) -> None:
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        row = connection.execute(
            "SELECT run_id FROM brief_daily WHERE tenant_id = %s AND brief_day = %s",
            (TENANT, BRIEF_DAY),
        ).fetchone()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "DELETE FROM brief_daily WHERE run_id = %s",
                (row[0],),
            )
