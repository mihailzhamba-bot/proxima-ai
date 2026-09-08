"""DB-тест детектора как шага сводки: сигналы на фактах nmId, отсутствие при
сводке не `ok`, `run_inputs`, детерминизм (AD-3, AD-9, AD-13, AD-19).

Запускается только из `tools/pg_local_roundtrip.sh`, где поднят одноразовый
PostgreSQL 16, применены миграции, разданы роли и экспортированы DSN. Без них
тест самопропускается, поэтому обычный `make test` его не гоняет.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import jsonschema
import psycopg
import pytest
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from proxima_control_plane.brief.cli import main as brief_main
from proxima_control_plane.norm.cli import main as norm_main

ROOT = Path(__file__).resolve().parents[4]
OWNER_DSN = os.environ.get("PROXIMA_TEST_POSTGRES_DSN", "")
NORM_DSN = os.environ.get("PROXIMA_TEST_DSN_NORM", "")
TENANT = "amirova-test"
# «Вчера» по календарю Europe/Moscow (AD-7): data_status_current свежий без подделки времени.
BRIEF_DAY = datetime.now(ZoneInfo("Europe/Moscow")).date() - timedelta(days=1)
# nm_id -> (заказы окна, заказы дня, выручка окна, выручка дня, предмет). Суммы по
# дням равны кабинетному ряду ниже: окно 38 / 3800.00, день 37 / 3700.00.
SKUS = {
    1001: (10, 5, Decimal("1000.00"), Decimal("500.00"), "Платье"),
    1002: (0, 0, Decimal("0.00"), Decimal("0.00"), "Платье"),
    1003: (20, 25, Decimal("2000.00"), Decimal("2500.00"), "Юбка"),
    1004: (8, 7, Decimal("800.00"), Decimal("700.00"), "Платье"),
}
CABINET_WINDOW = (38, Decimal("3800.00"))
CABINET_DAY = (37, Decimal("3700.00"))

pytestmark = pytest.mark.skipif(
    not (OWNER_DSN and NORM_DSN),
    reason="PROXIMA_TEST_POSTGRES_DSN and PROXIMA_TEST_DSN_NORM must be set (run via tools/pg_local_roundtrip.sh)",
)


def _days() -> list:
    return [BRIEF_DAY - timedelta(days=offset) for offset in range(14, -1, -1)]


@pytest.fixture
def seeded() -> tuple[str, str]:
    """Кабинетный ряд одним прогоном `collect`, ряд по nmId и словарь - вторым; после - уборка."""
    cabinet_run = str(uuid.uuid4())
    nm_run = str(uuid.uuid4())
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        owner.execute("INSERT INTO tenants (tenant_id) VALUES (%s) ON CONFLICT DO NOTHING", (TENANT,))
        owner.execute(
            "INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES (%s, %s, 'collect', 'SUCCEEDED', CURRENT_TIMESTAMP)",
            (cabinet_run, TENANT),
        )
        owner.execute(
            "INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at) VALUES (%s, %s, 'collect', 'SUCCEEDED', CURRENT_TIMESTAMP + interval '1 second')",
            (nm_run, TENANT),
        )
        for day in _days():
            orders, revenue = CABINET_DAY if day == BRIEF_DAY else CABINET_WINDOW
            owner.execute(
                """
                INSERT INTO fact_cabinet_daily
                    (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count,
                     returns_count, revenue_rub, forpay_rub, evidence_sha256)
                VALUES (%s, %s, %s, %s, 0, %s, 0, %s, %s, %s)
                """,
                (TENANT, day, cabinet_run, orders, orders, revenue, revenue, ["ab" * 32]),
            )
        for nm_id, (window_orders, day_orders, window_revenue, day_revenue, subject_name) in SKUS.items():
            owner.execute(
                """
                INSERT INTO dim_nm_subject
                    (tenant_id, nm_id, run_id, subject_name, category_name, brand, supplier_article, last_change_at, evidence_sha256)
                VALUES (%s, %s, %s, %s, 'Одежда', 'fixture-brand', %s, CURRENT_TIMESTAMP, %s)
                """,
                (TENANT, nm_id, nm_run, subject_name, f"ART-{nm_id}", "cd" * 32),
            )
            for day in _days():
                orders, revenue = (day_orders, day_revenue) if day == BRIEF_DAY else (window_orders, window_revenue)
                owner.execute(
                    """
                    INSERT INTO fact_nm_daily
                        (tenant_id, calendar_day, nm_id, run_id, orders_count, cancelled_count, sales_count,
                         returns_count, revenue_rub, forpay_rub, evidence_sha256)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, 0, %s, %s, %s)
                    """,
                    (TENANT, day, nm_id, nm_run, orders, orders, revenue, revenue, ["ef" * 32]),
                )
    yield cabinet_run, nm_run
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        # Зависимые прогоны первыми, входные collect - после (замыкание tools/delete_run.py, AD-3);
        # fact_nm_daily и dim_nm_subject уходят каскадом от collector_runs.
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'brief'", (TENANT,))
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'norm'", (TENANT,))
        owner.execute("DELETE FROM collector_runs WHERE tenant_id = %s AND kind = 'collect'", (TENANT,))


def _norm_and_brief() -> None:
    assert norm_main(["run", "--tenant", TENANT, "--date", BRIEF_DAY.isoformat()]) == 0
    assert brief_main(["run", "--tenant", TENANT, "--date", BRIEF_DAY.isoformat()]) == 0


def _briefs(connection: psycopg.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT b.status, b.payload, b.run_id::text
        FROM brief_daily b
        JOIN collector_runs r ON r.run_id = b.run_id
        WHERE b.tenant_id = %s AND b.brief_day = %s
        ORDER BY r.finished_at
        """,
        (TENANT, BRIEF_DAY),
    ).fetchall()
    assert rows, "brief_daily row is missing"
    return [{"status": row[0], "payload": row[1], "run_id": row[2]} for row in rows]


def _signal_validator() -> jsonschema.Draft202012Validator:
    schemas = [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((ROOT / "contracts").glob("*.schema.json"))]
    bases = [schema["$id"] for _, schema in schemas]
    resources = []
    for file_name, schema in schemas:
        for key in (schema["$id"], *(urljoin(base, file_name) for base in bases)):
            resources.append((key, DRAFT202012.create_resource(schema)))
    schema = json.loads((ROOT / "contracts" / "signal.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, registry=Registry().with_resources(resources))


def test_ok_brief_carries_ranked_schema_valid_signals_from_nm_facts(seeded: tuple[str, str]) -> None:
    cabinet_run, nm_run = seeded
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        brief = _briefs(connection)[-1]
    assert brief["status"] == "ok"
    signals = brief["payload"]["signals"]
    validator = _signal_validator()
    for signal in signals:
        validator.validate(signal)
    # Платье = 1001 + 1002 + 1004: 18 -> 12 (-33.3 %, 600.00); 1001: 10 -> 5 (500.00); 1004: 8 -> 7 (100.00).
    assert [s["rub_assessment"]["value_rub"] for s in signals] == ["600.00", "500.00", "100.00"]
    assert [s["detection_data"]["level"]["value"] for s in signals] == ["subject", "sku", "sku"]
    assert [s["detection_data"]["orders_deviation_pct"]["value"] for s in signals] == [-33.3, -50.0, -12.5]
    # Story 4.2: порог из конфигурации control-plane (detector/threshold.toml) - null до Story 4.4;
    # тройка записана в payload и в каждом сигнале, ни один кандидат ниже нормы не отсечён.
    assert brief["payload"]["threshold"] == {"value": None, "source": None, "date": None}
    for signal in signals:
        assert signal["detection_data"]["threshold_pct"] == {"value": None, "is_unknown": True}
        assert signal["detection_data"]["threshold_source"] == {"value": None, "is_unknown": True}
        assert signal["detection_data"]["threshold_date"] == {"value": None, "is_unknown": True}
    assert signals[1]["detection_data"]["nm_id"]["value"] == 1001
    assert signals[1]["detection_data"]["supplier_article"]["value"] == "ART-1001"
    assert signals[1]["detection_data"]["subject_name"]["value"] == "Платье"
    assert signals[1]["detection_data"]["funnel_stage"] == {"value": None, "is_unknown": True}
    refs = "\n".join(signals[1]["source_refs"])
    assert f"table://fact_nm_daily/nm/1001/run/{nm_run}" in refs
    assert f"table://dim_nm_subject/nm/1001/run/{nm_run}" in refs
    assert f"artifact://business-signal/sha256/{'ef' * 32}" in refs
    assert cabinet_run not in refs  # кабинетный ряд - вход сводки, не сигнала


def test_zero_norm_and_growth_skus_are_absent_and_the_payload_has_no_nan(seeded: tuple[str, str]) -> None:
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        row = connection.execute(
            "SELECT payload::text FROM brief_daily WHERE tenant_id = %s AND brief_day = %s",
            (TENANT, BRIEF_DAY),
        ).fetchone()
    text = row[0]
    payload = json.loads(text)
    nm_ids = {s["detection_data"]["nm_id"]["value"] for s in payload["signals"]}
    assert 1002 not in nm_ids  # нулевая норма: insufficient, без сигнала
    assert 1003 not in nm_ids  # рост: не кандидат
    assert "NaN" not in text and "Infinity" not in text
    assert payload["deviation_pct"]["orders"] == -2.6  # кабинетная сводка не изменилась


def test_run_inputs_include_every_run_the_detector_read(seeded: tuple[str, str]) -> None:
    cabinet_run, nm_run = seeded
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        inputs = connection.execute(
            """
            SELECT i.input_run_id::text
            FROM collector_run_inputs i
            JOIN collector_runs r ON r.run_id = i.run_id
            WHERE i.tenant_id = %s AND r.kind = 'brief'
            """,
            (TENANT,),
        ).fetchall()
    input_run_ids = {row[0] for row in inputs}
    assert {cabinet_run, nm_run} <= input_run_ids
    assert len(input_run_ids) == 3  # плюс прогон нормы


def test_insufficient_brief_carries_no_signals_even_with_sku_drops(seeded: tuple[str, str]) -> None:
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        for offset in range(5):
            day = BRIEF_DAY - timedelta(days=14 - offset)
            owner.execute("DELETE FROM fact_cabinet_daily WHERE tenant_id = %s AND calendar_day = %s", (TENANT, day))
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        brief = _briefs(connection)[-1]
        inputs = connection.execute(
            """
            SELECT count(*) FROM collector_run_inputs i
            JOIN collector_runs r ON r.run_id = i.run_id
            WHERE i.tenant_id = %s AND r.kind = 'brief'
            """,
            (TENANT,),
        ).fetchone()
    assert brief["status"] == "insufficient"
    assert brief["payload"]["signals"] == []  # ряд по nmId цел, но сводка не ok (PRD FR-7)
    assert inputs[0] == 2  # только кабинетный collect и норма: детектор не читал


def test_two_brief_runs_give_the_same_signals_and_snapshot(seeded: tuple[str, str]) -> None:
    _norm_and_brief()
    _norm_and_brief()
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        briefs = _briefs(connection)
    assert len(briefs) == 2

    def stable(signals: list[dict]) -> list[dict]:
        return [{key: value for key, value in signal.items() if key != "created_at"} for signal in signals]

    first, second = (brief["payload"]["signals"] for brief in briefs)
    assert stable(first) == stable(second)
    assert {s["snapshot_id"] for s in first} == {s["snapshot_id"] for s in second}
    assert len({s["snapshot_id"] for s in first}) == 1


def test_missing_dictionary_row_keeps_brief_succeeded_and_logs_one_warning(
    seeded: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        owner.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        owner.execute("DELETE FROM dim_nm_subject WHERE tenant_id = %s AND nm_id = 1001", (TENANT,))
    _norm_and_brief()
    output = capsys.readouterr().out.splitlines()
    warnings = [json.loads(line) for line in output if '"level": "warn"' in line]
    assert len(warnings) == 1
    assert warnings[0]["nm_ids"] == [1001]
    with psycopg.connect(NORM_DSN, autocommit=True) as connection:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (TENANT,))
        brief = _briefs(connection)[-1]
    assert brief["status"] == "ok"
    signal = next(item for item in brief["payload"]["signals"] if item["detection_data"]["nm_id"]["value"] == 1001)
    assert signal["detection_data"]["subject_name"] == {"value": None, "is_unknown": True}
    assert "table://dim_nm_subject/nm/1001/is_unknown" in signal["source_refs"]
