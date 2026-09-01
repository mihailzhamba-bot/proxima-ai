from datetime import datetime

import pytest

from proxima_control_plane.common.msk_day import msk_day


def test_msk_day_at_midnight_boundary() -> None:
    assert msk_day(datetime.fromisoformat("2026-08-29T21:00:00+00:00")).isoformat() == "2026-08-30"
    assert msk_day(datetime.fromisoformat("2026-08-29T20:59:59.999+00:00")).isoformat() == "2026-08-29"


def test_msk_day_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        msk_day(datetime(2026, 8, 29, 21, 0, 0))
