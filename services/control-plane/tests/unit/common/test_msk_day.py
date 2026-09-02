"""Midnight-boundary and parity tests for proxima_control_plane.common.msk_day.

Mirrors services/collector/tests/wb-msk-day.test.ts: both helpers must agree on
every input (AD-7) - the collector folds WB answers into fact_cabinet_daily by
this day, the norm job reads it back by the same day.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from zoneinfo import ZoneInfo

from proxima_control_plane.common.msk_day import msk_day, msk_today

MSK = ZoneInfo("Europe/Moscow")


class TestMskDayBoundary:
    """21:00Z is 00:00 MSK of the next day: the day must flip exactly there."""

    def test_just_before_midnight_stays_yesterday(self) -> None:
        assert msk_day("2026-08-29T20:59:59.999Z") == "2026-08-29"

    def test_exact_midnight_is_next_day(self) -> None:
        assert msk_day("2026-08-29T21:00:00Z") == "2026-08-30"

    def test_midnight_boundary_in_both_directions(self) -> None:
        assert msk_day("2026-08-30T20:59:59Z") == "2026-08-30"
        assert msk_day("2026-08-30T21:00:00Z") == "2026-08-31"


class TestMskDayZoneless:
    """WB sends Moscow wall clock without a zone (AD-7): read it as Moscow."""

    def test_zoneless_datetime_is_wall_clock_date(self) -> None:
        assert msk_day("2026-08-30T05:51:52") == "2026-08-30"

    def test_zoneless_date_is_itself(self) -> None:
        assert msk_day("2026-08-30") == "2026-08-30"

    def test_naive_datetime_takes_date_part(self) -> None:
        assert msk_day(datetime(2026, 8, 30, 5, 51, 52)) == "2026-08-30"


class TestMskDayAbsolute:
    def test_zulu_and_msk_offset_agree(self) -> None:
        assert msk_day("2026-08-29T21:00:00Z") == msk_day("2026-08-30T00:00:00+03:00")

    def test_naive_and_aware_wall_clock_agree(self) -> None:
        naive = datetime(2026, 8, 30, 5, 51, 52)
        aware = naive.replace(tzinfo=MSK)
        assert msk_day(naive) == msk_day(aware) == "2026-08-30"

    def test_aware_utc_datetime_converts(self) -> None:
        assert msk_day(datetime(2026, 8, 29, 21, 0, tzinfo=timezone.utc)) == "2026-08-30"

    def test_date_object_passes_through(self) -> None:
        assert msk_day(date(2026, 8, 30)) == "2026-08-30"

    def test_aware_datetime_in_far_zone_converts_to_msk(self) -> None:
        kamchatka = ZoneInfo("Asia/Kamchatka")
        # 2026-08-30T09:00+12:00 == 2026-08-29T21:00Z == 2026-08-30T00:00 MSK
        assert msk_day(datetime(2026, 8, 30, 9, 0, tzinfo=kamchatka)) == "2026-08-30"


class TestMskDayRejects:
    @pytest.mark.parametrize(
        "value",
        [
            "",
            "not-a-date",
            "2026-08-30T99:99:99Z",
            "2026-08-30T05:51:52+",
            123,
            None,
        ],
    )
    def test_invalid_input_raises(self, value: object) -> None:
        with pytest.raises(ValueError):
            msk_day(value)  # type: ignore[arg-type]


class TestMskDayParityWithCollector:
    """Pinned behavior of the TS twin (services/collector/src/wb/msk-day.ts),
    checked against the real node helper output when this suite was written."""

    def test_date_shaped_string_passes_through_unvalidated(self) -> None:
        # The TS regex branch returns the text as-is; calendar validity is the
        # caller's concern. Python does the same so both agree.
        assert msk_day("2026-13-01") == "2026-13-01"
        assert msk_day("2026-02-30") == "2026-02-30"

    def test_wall_clock_text_without_zone_takes_date_part(self) -> None:
        assert msk_day("2026-08-30 05:51:52") == "2026-08-30"

    def test_lenient_forms_diverge_from_node(self) -> None:
        """Documented divergence: V8's Date.parse accepts single-digit fields
        ('2026-8-30' -> 2026-08-30); the control plane stays strict. The WB API
        only emits zero-padded ISO-8601, so this input cannot reach either side."""
        with pytest.raises(ValueError):
            msk_day("2026-8-30")


class TestMskToday:
    def test_utc_instant_before_msk_midnight(self) -> None:
        assert msk_today(datetime(2026, 8, 29, 20, 59, 59, tzinfo=timezone.utc)) == "2026-08-29"

    def test_utc_instant_after_msk_midnight(self) -> None:
        assert msk_today(datetime(2026, 8, 29, 21, 0, 0, tzinfo=timezone.utc)) == "2026-08-30"

    def test_now_is_a_valid_day(self) -> None:
        assert msk_today().count("-") == 2


class TestRuntimeZoneIndependence:
    def test_result_does_not_depend_on_runtime_zone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The same instant must fold to the same Moscow day under any TZ."""
        instant_utc = datetime(2026, 8, 29, 21, 0, 0, tzinfo=timezone.utc)
        baseline = msk_day(instant_utc)
        for tz in ("Asia/Kamchatka", "America/New_York", "UTC"):
            monkeypatch.setenv("TZ", tz)
            try:
                import time

                time.tzset()
            except AttributeError:  # pragma: no cover - non-POSIX
                continue
            assert msk_day(instant_utc) == baseline
            assert msk_day("2026-08-29T21:00:00Z") == baseline

    def test_msk_offset_is_three_hours_for_tested_range(self) -> None:
        """Russia has had no DST since 2014; assert +03:00 across the year."""
        for month in range(1, 13):
            instant = datetime(2026, month, 15, 12, 0, tzinfo=timezone.utc)
            wall = instant.astimezone(MSK).utcoffset()
            assert wall == timedelta(hours=3)
