import os
import random
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from helpers import run_detect, synth_bundle, synth_row
from proxima_control_plane.detectors.scn001 import DedupEntry
from proxima_control_plane.detectors.scn001.clock import MOSCOW_TZ, default_evaluation_date
from proxima_control_plane.detectors.scn001.metrics import DailyMetrics, MetricBundle

EVAL = date(2026, 8, 27)
SKU = "SYNTH-SKU-1"


def test_drop_case_proposes_signal_with_exact_contribution_sum():
    bundle = synth_bundle(EVAL, [{"sku": SKU, "orders": 65, "open_card": 200, "aov": 1000}])
    result = run_detect(bundle, EVAL)

    sku_signals = [s for s in result.signals if s.level == "sku"]
    assert len(sku_signals) == 1
    signal = sku_signals[0]
    assert signal.level == "sku"
    assert signal.key == SKU
    assert signal.revenue_delta_orders.value == Decimal("35000")
    assert signal.revenue_delta_orders.method == "revenue"
    assert signal.contributions.u == 0
    assert signal.contributions.aov == 0
    assert signal.contributions.cvr == Decimal("35000")
    assert signal.contributions.total() == signal.revenue_delta_orders.value
    assert signal.dominant_factor == "cvr"
    assert signal.delta_28 == Decimal("-0.35")
    assert signal.delta_7 == Decimal("-0.35")
    assert signal.delta_14 == Decimal("-0.35")


def test_seasonal_weekend_drop_does_not_fire():
    eval_sunday = date(2026, 8, 2)
    rows = []
    for offset in range(28, 0, -1):
        day = eval_sunday - timedelta(days=offset)
        weekend_orders = 50 if day.weekday() >= 5 else 100
        rows.append(synth_row(SKU, day, weekend_orders))
    rows.append(synth_row(SKU, eval_sunday, 50))
    bundle = MetricBundle.build(rows)
    result = run_detect(bundle, eval_sunday)

    assert result.signals == ()
    assert result.blocked == ()
    assert result.counters.candidates == 0


def test_drop_without_corroboration_does_not_fire():
    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(
        eval_date,
        [{"sku": SKU, "orders": 90}],
        history_orders_fn=lambda offset: Decimal(120) if offset >= 8 else Decimal(100),
    )
    result = run_detect(bundle, eval_date)

    assert result.signals == ()
    assert result.blocked == ()


def test_dedup_entries_created_only_for_emitted_signals():
    eval_date = date(2026, 8, 27)

    class HugeFloorSource:
        def drop_threshold(self) -> Decimal:
            return Decimal("0.20")

        def rub_floor(self) -> Decimal:
            return Decimal("1000000000")

    bundle = synth_bundle(eval_date, [{"sku": SKU, "orders": 65}])
    filtered = run_detect(bundle, eval_date, source=HugeFloorSource())

    assert filtered.signals == ()
    assert filtered.dedup_state == (), "no dedup records when every candidate is filtered"

    rerun = run_detect(bundle, eval_date, dedup_state=filtered.dedup_state)
    assert any(s.level == "sku" for s in rerun.signals), (
        "later significant signals must not be suppressed by phantom dedup records"
    )


def test_dedup_lifecycle_suppress_recovery_midzone_cooldown():
    x1 = date(2026, 8, 17)
    x2 = date(2026, 8, 18)
    x3 = date(2026, 8, 19)
    x4 = date(2026, 8, 20)
    x5 = date(2026, 8, 21)

    r1 = run_detect(synth_bundle(x1, [{"sku": SKU, "orders": 65}]), x1)
    assert len([s for s in r1.signals if s.level == "sku"]) == 1
    entry = next(e for e in r1.dedup_state if e.key == SKU)
    assert entry.opened_at == x1
    assert entry.last_seen_date == x1

    r2 = run_detect(
        synth_bundle(x2, [{"sku": SKU, "orders": 65}]), x2, dedup_state=r1.dedup_state
    )
    assert [s for s in r2.signals if s.level == "sku"] == []
    assert r2.counters.dedup_suppressed == 2
    entry2 = next(e for e in r2.dedup_state if e.key == SKU)
    assert entry2.opened_at == x1
    assert entry2.last_seen_date == x2

    midzone = synth_bundle(
        x3,
        [{"sku": SKU, "orders": 90}],
        history_orders_fn=lambda offset: Decimal(120) if offset >= 8 else Decimal(100),
    )
    r3 = run_detect(midzone, x3, dedup_state=r2.dedup_state)
    assert [s for s in r3.signals if s.level == "sku"] == []
    assert r3.counters.dedup_suppressed == 0
    entry3 = next(e for e in r3.dedup_state if e.key == SKU)
    assert entry3.opened_at == x1
    assert entry3.last_seen_date == x2

    r4 = run_detect(
        synth_bundle(x4, [{"sku": SKU, "orders": 100}]), x4, dedup_state=r3.dedup_state
    )
    assert r4.dedup_state == ()

    r5 = run_detect(
        synth_bundle(x5, [{"sku": SKU, "orders": 65}]), x5, dedup_state=r4.dedup_state
    )
    assert len([s for s in r5.signals if s.level == "sku"]) == 1
    assert next(e for e in r5.dedup_state if e.key == SKU).opened_at == x5


def test_dedup_cooldown_reopens_from_last_seen():
    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(eval_date, [{"sku": SKU, "orders": 65}])

    fresh_state = (
        DedupEntry(level="sku", key=SKU, opened_at=eval_date - timedelta(days=10), last_seen_date=eval_date - timedelta(days=7)),
    )
    reopened = run_detect(bundle, eval_date, dedup_state=fresh_state)
    assert len([s for s in reopened.signals if s.level == "sku"]) == 1
    assert reopened.counters.dedup_suppressed == 0
    entry = next(e for e in reopened.dedup_state if e.key == SKU)
    assert entry.opened_at == eval_date

    recent_state = (
        DedupEntry(level="sku", key=SKU, opened_at=eval_date - timedelta(days=10), last_seen_date=eval_date - timedelta(days=6)),
    )
    suppressed = run_detect(bundle, eval_date, dedup_state=recent_state)
    assert [s for s in suppressed.signals if s.level == "sku"] == []
    assert suppressed.counters.dedup_suppressed == 1
    assert next(e for e in suppressed.dedup_state if e.key == SKU).last_seen_date == eval_date


def test_rub_floor_counts_only_floor_cuts_rank_cut_separate():
    eval_date = date(2026, 8, 27)
    specs = [
        {
            "sku": f"SYNTH-SKU-{i:02d}",
            "orders": 50,
            "aov": Decimal(1000) - Decimal(50) * i,
        }
        for i in range(12)
    ]
    specs.extend(
        {
            "sku": f"SYNTH-SKU-{i:02d}",
            "orders": 5,
            "aov": 100,
            "history_orders": 10,
            "history_aov": 100,
        }
        for i in range(12, 15)
    )
    bundle = synth_bundle(eval_date, specs)
    result = run_detect(bundle, eval_date)

    assert result.counters.candidates == 16
    assert result.counters.filtered_by_rub == 3
    assert result.counters.filtered_by_rank == 3
    assert len(result.signals) == 10
    assert result.signals[0].level == "cabinet"
    emitted_skus = [s.key for s in result.signals if s.level == "sku"]
    assert emitted_skus == [f"SYNTH-SKU-{i:02d}" for i in range(11, 2, -1)]
    for signal in result.signals:
        assert signal.revenue_delta_orders.value >= Decimal("3000")


def test_cabinet_signal_on_distributed_drop_below_floor():
    eval_date = date(2026, 8, 27)
    specs = [
        {
            "sku": f"SYNTH-SKU-{i:02d}",
            "orders": 1,
            "open_card": 4,
            "aov": 500,
            "history_orders": 2,
            "history_open_card": 4,
            "history_aov": 500,
        }
        for i in range(30)
    ]
    bundle = synth_bundle(eval_date, specs)
    result = run_detect(bundle, eval_date)

    assert result.counters.candidates == 31
    assert result.counters.filtered_by_rub == 30
    assert result.counters.filtered_by_rank == 0
    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.level == "cabinet"
    assert signal.key == "__cabinet__"
    assert signal.panel_size == 30
    assert signal.excluded_count == 0
    assert signal.delta_28 == Decimal("-0.5")
    assert signal.revenue_delta_orders.value == Decimal("15000")
    assert signal.revenue_delta_orders.value >= Decimal("3000")


def test_maturity_fallback_without_evaluation_date_keeps_full_series():
    eval_date = date(2026, 8, 27)
    rows21 = [synth_row(SKU, eval_date - timedelta(days=o), 100) for o in range(21, 0, -1)]
    bundle = MetricBundle.build(rows21)
    assert bundle.panel == (SKU,)
    assert bundle.excluded == ()

    rows20 = [synth_row(SKU, eval_date - timedelta(days=o), 100) for o in range(20, 0, -1)]
    bundle20 = MetricBundle.build(rows20)
    assert bundle20.panel == ()
    assert bundle20.excluded == (SKU,)


def test_maturity_window_excludes_evaluation_day_strictly():
    eval_date = date(2026, 8, 27)
    rows = [synth_row(SKU, eval_date - timedelta(days=o), 100) for o in range(20, 0, -1)]
    rows.append(synth_row(SKU, eval_date, 65))
    bundle = MetricBundle.build(rows, evaluation_date=eval_date)

    assert bundle.panel == ()
    assert bundle.excluded == (SKU,)

    result = run_detect(bundle, eval_date)
    blocked = {(e.level, e.key): e.reason for e in result.blocked}
    assert blocked.get(("sku", SKU)) == "INSUFFICIENT_HISTORY"
    assert result.signals == (), "cabinet signal must not fire from an out-of-panel SKU"


def test_blocked_reasons_insufficient_history_invalid_baseline_invalid_input():
    eval_date = date(2026, 8, 27)
    rows = []
    for offset in range(11, 0, -1):
        rows.append(synth_row("SYNTH-SKU-A", eval_date - timedelta(days=offset), 100))
    rows.append(synth_row("SYNTH-SKU-A", eval_date, 100))
    for offset in range(29, 0, -1):
        rows.append(synth_row("SYNTH-SKU-B", eval_date - timedelta(days=offset), 0, 0, 0))
    for offset in range(28, 0, -1):
        rows.append(synth_row("SYNTH-SKU-C", eval_date - timedelta(days=offset), 100))
    rows.append(synth_row("SYNTH-SKU-C", eval_date, 5, 0, 1000))
    bundle = MetricBundle.build(rows)
    result = run_detect(bundle, eval_date)

    reasons = {(e.level, e.key): e.reason for e in result.blocked}
    assert reasons[("sku", "SYNTH-SKU-A")] == "INSUFFICIENT_HISTORY"
    assert reasons[("sku", "SYNTH-SKU-B")] == "INVALID_BASELINE"
    assert reasons[("sku", "SYNTH-SKU-C")] == "INVALID_INPUT"
    assert result.counters.blocked_by_reason == {
        "INSUFFICIENT_HISTORY": 1,
        "INVALID_BASELINE": 1,
        "INVALID_INPUT": 2,
    }
    for entry in result.blocked:
        assert entry.trust_marking == "unreleased"
    assert result.signals == ()


def test_negative_metrics_blocked_invalid_input_not_silent_baseline():
    eval_date = date(2026, 8, 27)
    rows = []
    for offset in range(28, 0, -1):
        rows.append(synth_row("SYNTH-SKU-D", eval_date - timedelta(days=offset), 100))
    rows.append(synth_row("SYNTH-SKU-D", eval_date, -5))
    for offset in range(28, 0, -1):
        rows.append(
            synth_row("SYNTH-SKU-E", eval_date - timedelta(days=offset), 100, buyouts=-1)
        )
    rows.append(synth_row("SYNTH-SKU-E", eval_date, 100))
    bundle = MetricBundle.build(rows)
    result = run_detect(bundle, eval_date)

    reasons = {(e.level, e.key): e.reason for e in result.blocked}
    assert reasons[("sku", "SYNTH-SKU-D")] == "INVALID_INPUT"
    assert reasons[("sku", "SYNTH-SKU-E")] == "INVALID_INPUT"
    assert reasons[("cabinet", "__cabinet__")] == "INVALID_INPUT"
    assert result.counters.blocked_by_reason == {"INVALID_INPUT": 3}
    assert result.signals == ()


def test_shapley_exact_sum_with_two_changing_factors_hand_computed():
    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(
        eval_date, [{"sku": SKU, "orders": 30, "open_card": 100, "aov": 1500}]
    )
    result = run_detect(bundle, eval_date)

    signal = next(s for s in result.signals if s.level == "sku")
    assert signal.revenue_delta_orders.value == Decimal("55000")
    assert signal.contributions.u == Decimal("49166.66666666666666666666667")
    assert signal.contributions.cvr == Decimal("36666.66666666666666666666667")
    assert signal.contributions.aov == Decimal("-30833.33333333333333333333334")
    assert signal.contributions.total() == signal.revenue_delta_orders.value
    assert signal.dominant_factor == "u"


def test_collapse_zero_orders_day_gives_full_contribution_without_crash():
    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(eval_date, [{"sku": SKU, "orders": 0, "open_card": 200}])
    result = run_detect(bundle, eval_date)

    signal = next(s for s in result.signals if s.level == "sku")
    assert signal.revenue_delta_orders.value == Decimal("100000")
    assert signal.contributions.cvr == Decimal("100000")
    assert signal.contributions.u == 0
    assert signal.contributions.aov == 0
    assert signal.contributions.total() == signal.revenue_delta_orders.value
    assert signal.dominant_factor == "cvr"
    assert signal.delta_28 == Decimal("-1")


def test_determinism_input_order_and_excluded_sku_invariance():
    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(eval_date, [{"sku": SKU, "orders": 65}])
    r1 = run_detect(bundle, eval_date)
    r2 = run_detect(synth_bundle(eval_date, [{"sku": SKU, "orders": 65}]), eval_date)

    assert r1 == r2
    assert r1.snapshot_id == r2.snapshot_id
    assert r1.run_fingerprint == r2.run_fingerprint

    rows = [
        synth_row(SKU, eval_date - timedelta(days=o), 100) for o in range(28, 0, -1)
    ] + [synth_row(SKU, eval_date, 65)]
    random.Random(7).shuffle(rows)
    shuffled = run_detect(MetricBundle.build(rows), eval_date)

    assert shuffled.snapshot_id == r1.snapshot_id
    assert shuffled.signals == r1.signals
    assert shuffled.run_fingerprint == r1.run_fingerprint

    rows_with_excluded = rows + [synth_row("SYNTH-SKU-EXTRA", eval_date, 50)]
    with_excluded = run_detect(MetricBundle.build(rows_with_excluded), eval_date)
    assert with_excluded.snapshot_id == r1.snapshot_id
    assert [s for s in with_excluded.signals if s.level == "sku"] == [
        s for s in r1.signals if s.level == "sku"
    ]
    assert any(
        e.key == "SYNTH-SKU-EXTRA" and e.reason == "INSUFFICIENT_HISTORY"
        for e in with_excluded.blocked
    )


def test_report_profile_fields():
    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(eval_date, [{"sku": SKU, "orders": 65}])
    result = run_detect(bundle, eval_date)

    assert result.evaluation_date == eval_date
    assert result.trust_marking == "unreleased"
    assert len(result.run_fingerprint) == 64
    signal = next(s for s in result.signals if s.level == "sku")
    assert signal.scenario_code == "SCN-001"
    assert signal.trust_marking == "unreleased"
    assert signal.source_refs == ()
    assert signal.evaluation_date == eval_date
    assert len(signal.snapshot_id) == 64
    assert signal.revenue_delta_orders.method == "revenue"
    assert signal.factors_actual.cvr == Decimal("0.325")
    assert signal.factors_baseline.cvr == Decimal("0.5")

    other_day = date(2026, 8, 26)
    replay = run_detect(bundle, other_day)
    assert replay.evaluation_date == other_day
    assert replay.snapshot_id != result.snapshot_id


def test_threshold_source_override_changes_result():
    class StubPassportSource:
        def drop_threshold(self) -> Decimal:
            return Decimal("0.50")

        def rub_floor(self) -> Decimal:
            return Decimal("3000")

    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(eval_date, [{"sku": SKU, "orders": 65}])

    with_default = run_detect(bundle, eval_date)
    with_stub = run_detect(bundle, eval_date, source=StubPassportSource())

    assert any(s.level == "sku" for s in with_default.signals)
    assert not any(s.level == "sku" for s in with_stub.signals)
    assert with_default.counters.candidates >= 1
    assert with_stub.counters.candidates == 0


def test_detector_core_has_no_llm_or_io_imports():
    import proxima_control_plane.detectors.scn001 as pkg

    forbidden = (
        "openai",
        "anthropic",
        "psycopg",
        "urllib",
        "httpx",
        "requests",
        "socket",
        "llm",
    )
    # spec «Loader»/«Smoke»: psycopg (единственный шов к БД) разрешён только в этих файлах;
    # LLM/сетевые импорты запрещены во всём пакете (R15).
    db_seam_files = {"loader.py", "smoke.py"}
    for path in Path(pkg.__file__).parent.rglob("*.py"):
        checked = (
            tuple(t for t in forbidden if t != "psycopg") if path.name in db_seam_files else forbidden
        )
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(("import ", "from ")):
                low = line.lower()
                assert not any(token in low for token in checked), f"{path}: {line}"


def test_canonical_hash_stable_across_python_hash_seeds():
    script = (
        "from datetime import date;"
        "from decimal import Decimal;"
        "from proxima_control_plane.detectors.scn001 import canonical_hash;"
        "obj = {'a': {Decimal(str(i)) for i in range(12)}, 'b': [date(2026, 1, 1)], 'c': {'x': Decimal('3.50')}};"
        "print(canonical_hash(obj))"
    )
    outputs = []
    for seed in ("0", "1"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        proc = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env
        )
        assert proc.returncode == 0, proc.stderr
        outputs.append(proc.stdout.strip())
    assert outputs[0] == outputs[1]
    assert len(outputs[0]) == 64


def test_zero_traffic_baseline_collapse_contributes_exactly():
    eval_date = date(2026, 8, 27)
    bundle = synth_bundle(
        eval_date,
        [{"sku": SKU, "orders": 65, "open_card": 200, "aov": 1000, "history_open_card": 0}],
    )
    result = run_detect(bundle, eval_date)

    signal = next(s for s in result.signals if s.level == "sku")
    assert signal.factors_baseline.u == 0
    assert signal.factors_baseline.cvr == 0
    assert signal.revenue_delta_orders.value == Decimal("35000")
    assert signal.contributions.u == Decimal("35000")
    assert signal.contributions.cvr == 0
    assert signal.contributions.aov == 0
    assert signal.contributions.total() == signal.revenue_delta_orders.value
    assert signal.dominant_factor == "u"


def test_dedup_entry_removed_at_exact_recovery_threshold():
    x1 = date(2026, 8, 17)
    x2 = date(2026, 8, 18)
    r1 = run_detect(synth_bundle(x1, [{"sku": SKU, "orders": 65}]), x1)
    assert len(r1.dedup_state) == 2

    boundary = synth_bundle(
        x2,
        [{"sku": SKU, "orders": 86}],
        history_orders_fn=lambda offset: Decimal(110) if offset >= 8 else Decimal(100),
    )
    r2 = run_detect(boundary, x2, dedup_state=r1.dedup_state)
    assert [s for s in r2.signals if s.level == "sku"] == []
    assert r2.counters.dedup_suppressed == 0
    assert r2.dedup_state == ()


def test_non_finite_decimal_rejected_at_input_not_deep_invalid_operation():
    with pytest.raises(ValueError) as nan_exc:
        DailyMetrics(
            sku="SYNTH-NAN",
            date=EVAL,
            orders=Decimal("NaN"),
            open_card=Decimal("200"),
            orders_sum_rub=Decimal("0"),
            buyouts=Decimal("0"),
        )
    assert "finite" in str(nan_exc.value)
    with pytest.raises(ValueError):
        DailyMetrics(
            sku="SYNTH-INF",
            date=EVAL,
            orders=Decimal("1"),
            open_card=Decimal("200"),
            orders_sum_rub=Decimal("Infinity"),
            buyouts=Decimal("0"),
        )
    with pytest.raises(ValueError):
        DailyMetrics(
            sku="SYNTH-NANSTR",
            date=EVAL,
            orders="NaN",
            open_card=Decimal("200"),
            orders_sum_rub=Decimal("0"),
            buyouts=Decimal("0"),
        )


def test_default_evaluation_date_helper_returns_yesterday_moscow():
    # Asserts only on injected `now` cases: comparing two live now() calls is
    # flaky across the Moscow midnight boundary (repair W3).
    assert default_evaluation_date(datetime(2026, 8, 28, 1, 30, tzinfo=MOSCOW_TZ)) == date(2026, 8, 27)
    assert default_evaluation_date(datetime(2026, 8, 28, 0, 30, tzinfo=timezone.utc)) == date(2026, 8, 27)
    assert default_evaluation_date(datetime(2026, 1, 1, 0, 0, tzinfo=MOSCOW_TZ)) == date(2025, 12, 31)
