import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import glm_tariff as tariff


UTC8 = timezone(timedelta(hours=8))
MSK = timezone(timedelta(hours=3))


def at(day, hour, minute=0, second=0, tz=UTC8):
    return datetime(2026, 9, day, hour, minute, second, tzinfo=tz)


@pytest.mark.parametrize(('now', 'allowed', 'reason'), [
    (at(16, 13, 57, 55), True, 'off_peak'),
    (at(16, 13, 57, 56), False, 'pre_peak_guard_band'),
    (at(16, 14), False, 'weekday_peak'),
    (at(16, 17, 59, 59), False, 'weekday_peak'),
    (at(16, 18), True, 'off_peak'),
])
def test_weekday_boundaries_include_timeout_and_buffer(now, allowed, reason):
    result = tariff.tariff_status(now, request_seconds=120)
    assert result['allowed'] is allowed
    assert result['reason'] == reason


def test_peak_resume_is_same_day_18_fixed_utc8():
    result = tariff.tariff_status(at(16, 14))
    assert result['resume_at'] == int(at(16, 18).astimezone(timezone.utc).timestamp())


@pytest.mark.parametrize(('now', 'allowed', 'reason'), [
    (at(18, 18), True, 'off_peak'),       # Friday after peak
    (at(19, 14), True, 'off_peak'),       # Saturday
    (at(20, 14), True, 'off_peak'),       # Sunday
    (at(21, 13, 57, 56), False, 'pre_peak_guard_band'),  # Monday
    (at(21, 14), False, 'weekday_peak'),
])
def test_weekend_rolls_to_monday(now, allowed, reason):
    result = tariff.tariff_status(now)
    assert result['allowed'] is allowed
    assert result['reason'] == reason


def test_same_instant_in_utc_and_moscow_has_same_peak_result():
    utc_now = datetime(2026, 9, 16, 6, tzinfo=timezone.utc)
    moscow_now = at(16, 9, tz=MSK)
    assert utc_now == moscow_now
    assert tariff.tariff_status(utc_now) == tariff.tariff_status(moscow_now)
    assert tariff.tariff_status(moscow_now)['reason'] == 'weekday_peak'


def test_naive_datetime_rejected():
    with pytest.raises(ValueError, match='aware_datetime_required'):
        tariff.tariff_status(datetime(2026, 9, 16, 8))


@pytest.mark.parametrize('budget', [True, 0, -1, 121, float('nan'), '120', None])
def test_invalid_request_budget_rejected(budget):
    with pytest.raises(ValueError, match='invalid_request_seconds'):
        tariff.tariff_status(at(16, 8), budget)


def test_require_offpeak_exposes_deferred_fields(monkeypatch):
    resume = 1_800_000_000
    monkeypatch.setattr(tariff, 'tariff_status',
        lambda **_kwargs: {'allowed': False, 'reason': 'weekday_peak', 'resume_at': resume})
    with pytest.raises(tariff.TariffDeferred) as caught:
        tariff.require_offpeak(60)
    assert caught.value.as_dict() == {'reason': 'weekday_peak', 'resume_at': resume}


def test_check_cli_prints_json_without_request(monkeypatch, capsys):
    expected = {'allowed': True, 'reason': 'off_peak', 'resume_at': None}
    monkeypatch.setattr(tariff, 'tariff_status', lambda: expected)
    monkeypatch.setattr(sys, 'argv', ['glm_tariff.py', '--check'])
    assert tariff.main() == 0
    assert json.loads(capsys.readouterr().out) == expected
