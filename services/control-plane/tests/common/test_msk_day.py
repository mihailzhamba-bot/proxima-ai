from datetime import datetime

from proxima_control_plane.common.msk_day import msk_day


def test_msk_day_at_midnight_boundary() -> None:
    assert msk_day(datetime.fromisoformat("2026-08-29T23:30:00+00:00")).isoformat() == "2026-08-30"
    assert msk_day(datetime.fromisoformat("2026-08-29T20:59:59+00:00")).isoformat() == "2026-08-29"
