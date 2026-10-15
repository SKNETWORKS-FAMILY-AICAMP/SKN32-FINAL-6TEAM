"""수신 직후에도 공급 자료가 오래되거나 미래인 응답을 새 예측으로 사용하면 안 된다."""
from copy import deepcopy
from datetime import timedelta, timezone

import pytest

from .test_bus_boardable_arrival_v1 import NOW, choose, snapshot


def frame(at):
    data = snapshot()
    data['stops'][0]['received_at'] = at
    return data


def test_fresh_response_with_twenty_minute_old_provider_frame_requires_refresh():
    data = frame((NOW - timedelta(minutes=20)).isoformat())
    saved = deepcopy(data)
    result = choose(data)
    assert result['status'] == 'stale' and result['reason'] == 'provider_refresh_required'
    assert result['observation_age_seconds'] == 0 and result['provider_age_seconds'] == 1200
    assert 'remaining_seconds' not in result and data == saved


@pytest.mark.parametrize('age,status', [(89, 'predicted'), (90, 'predicted'), (90.001, 'stale')])
def test_provider_age_boundary_is_independent_of_cache_ttl(age, status):
    assert choose(frame((NOW - timedelta(seconds=age)).isoformat()))['status'] == status


def test_cached_provider_age_is_recalculated_from_original_stamp():
    data = frame((NOW - timedelta(seconds=80)).isoformat())
    data['stops'][0]['received_age_seconds'] = 80
    result = choose(data, now=NOW + timedelta(seconds=20))
    assert result['observation_age_seconds'] == 20 and result['provider_age_seconds'] == 100
    assert result['status'] == 'stale'


@pytest.mark.parametrize('offset,status', [(1, 'predicted'), (2, 'predicted'), (2.001, 'unavailable')])
def test_future_provider_clock_has_an_explicit_limit(offset, status):
    result = choose(frame((NOW + timedelta(seconds=offset)).isoformat()))
    assert result['status'] == status
    if status == 'unavailable':
        assert result['reason'] == 'provider_clock_in_future'


@pytest.mark.parametrize('value', [None, '', 'not-a-time', '2026-99-99 10:00:00'])
def test_missing_or_invalid_provider_time_is_not_replaced_by_now(value):
    assert choose(frame(value))['reason'] == 'invalid_provider_received_at'


def test_naive_provider_time_uses_kst_and_preserves_original_text():
    raw = '2026-10-09 09:59:52.0'
    result = choose(frame(raw))
    assert result['status'] == 'predicted' and result['provider_age_seconds'] == 8
    assert result['provider_received_at'] == raw
    assert result['provider_received_at_normalized'] == '2026-10-09T09:59:52+09:00'


def test_offset_aware_provider_time_is_not_relabelled_as_kst():
    result = choose(frame((NOW - timedelta(seconds=8)).astimezone(timezone.utc).isoformat()))
    assert result['provider_age_seconds'] == 8
    assert result['provider_received_at_normalized'].endswith('+00:00')


def test_provider_age_is_not_subtracted_from_eta_a_second_time():
    result = choose(frame((NOW - timedelta(seconds=15)).isoformat()),
                    now=NOW + timedelta(seconds=20), ready=390)
    assert result['provider_age_seconds'] == 35
    assert result['remaining_seconds'] == 400 and result['wait_after_access_seconds'] == 10


@pytest.mark.parametrize('parameter,value,reason', [
    ('max_provider_age_seconds', 0, 'invalid_provider_age_limit'),
    ('max_provider_age_seconds', True, 'invalid_provider_age_limit'),
    ('max_provider_age_seconds', float('nan'), 'invalid_provider_age_limit'),
    ('max_provider_age_seconds', float('inf'), 'invalid_provider_age_limit'),
    ('max_provider_age_seconds', '90', 'invalid_provider_age_limit'),
    ('max_provider_clock_ahead_seconds', -1, 'invalid_provider_clock_limit'),
    ('max_provider_clock_ahead_seconds', False, 'invalid_provider_clock_limit'),
    ('max_provider_clock_ahead_seconds', float('nan'), 'invalid_provider_clock_limit'),
    ('max_provider_clock_ahead_seconds', float('inf'), 'invalid_provider_clock_limit'),
    ('max_provider_clock_ahead_seconds', '2', 'invalid_provider_clock_limit'),
])
def test_invalid_freshness_policy_cannot_disable_checks(parameter, value, reason):
    assert choose(**{parameter: value})['reason'] == reason


def test_zero_clock_skew_tolerance_is_valid_policy():
    assert choose(max_provider_clock_ahead_seconds=0)['status'] == 'predicted'
    assert choose(frame((NOW + timedelta(microseconds=1)).isoformat()),
                  max_provider_clock_ahead_seconds=0)['reason'] == 'provider_clock_in_future'


def test_past_ready_time_is_not_silently_clamped_to_immediate_boarding():
    assert choose(ready=-1)['reason'] == 'invalid_ready_at'
