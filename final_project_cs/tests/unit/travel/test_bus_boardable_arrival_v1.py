"""접근 중 놓치는 차량과 캐시 재사용 시간이 탑승 예상에 반영돼야 한다."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from app.domains.travel_ops.ports.data_sources.seoul_bus import KST, select_boardable_arrival

NOW = datetime(2026, 10, 9, 10, 0, tzinfo=KST)


def snapshot(first=180, second=420):
    return {'kind': 'bus_arrival', 'source': 'seoul_bus_arrival', 'route_id': '100',
            'confirmed_at': NOW.isoformat(), 'stops': [
                {'stop_id': '101', 'stop_sequence': 5, 'received_at': (NOW - timedelta(seconds=8)).isoformat(),
                 'direction': '서울역', 'buses': [
                     {'order': 1, 'eta_seconds': first, 'eta_basis': 'provider_message', 'full': False},
                     {'order': 2, 'eta_seconds': second, 'eta_basis': 'provider_message', 'full': False}]}]}


def choose(data=None, *, now=NOW, ready=360, **overrides):
    params = dict(route_id='100', stop_id='101', stop_sequence=5, now=now,
                  ready_at=now + timedelta(seconds=ready), max_age_seconds=30,
                  max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2)
    params.update(overrides)
    return select_boardable_arrival(snapshot() if data is None else data, **params)


def test_six_minute_access_skips_bus_in_three_minutes_and_selects_second():
    data = snapshot()
    saved = deepcopy(data)
    result = choose(data)
    assert result['status'] == 'predicted' and result['bus_order'] == 2
    assert result['remaining_seconds'] == 420 and result['wait_after_access_seconds'] == 60
    assert result['arrival_at'] == (NOW + timedelta(seconds=420)).isoformat()
    assert data == saved


def test_only_cache_elapsed_is_subtracted_and_provider_age_is_not_subtracted_twice():
    result = choose(now=NOW + timedelta(seconds=20), ready=390)
    assert result['bus_order'] == 2 and result['remaining_seconds'] == 400
    assert result['wait_after_access_seconds'] == 10
    assert result['confirmed_at'] == NOW.isoformat()
    assert result['provider_received_at'] == (NOW - timedelta(seconds=8)).isoformat()


def test_exact_ready_time_is_boardable_but_one_second_later_is_not():
    assert choose(snapshot(360, 420))['bus_order'] == 1
    assert choose(snapshot(359, 420))['bus_order'] == 2


def test_full_and_unknown_message_are_not_zero_second_buses():
    data = snapshot(420, None)
    data['stops'][0]['buses'][0]['full'] = True
    result = choose(data)
    assert result['status'] == 'no_boardable_prediction'
    assert {row['reason'] for row in result['excluded']} == {'full', 'no_numeric_eta'}
    assert 'remaining_seconds' not in result


@pytest.mark.parametrize('changes,reason', [
    ({'route_id': '200'}, 'source_or_route_mismatch'), ({'stop_id': '102'}, 'stop_not_unique'),
    ({'stop_sequence': 6}, 'stop_not_unique'), ({'stop_sequence': True}, 'invalid_stop_identity'),
    ({'now': NOW.replace(tzinfo=None)}, 'timezone_required'),
    ({'max_age_seconds': float('nan')}, 'invalid_age_limit'),
])
def test_invalid_identity_and_clock_do_not_match_another_stop(changes, reason):
    result = choose(**changes)
    assert result['status'] == 'unavailable' and result['reason'] == reason


def test_duplicate_stop_sequence_is_not_silently_selected():
    data = snapshot()
    data['stops'].append(deepcopy(data['stops'][0]))
    assert choose(data)['reason'] == 'stop_not_unique'


def test_stale_and_future_confirmations_require_refresh():
    assert choose(now=NOW + timedelta(seconds=30))['status'] == 'stale'
    assert choose(now=NOW - timedelta(seconds=1))['reason'] == 'confirmation_in_future'


def test_second_order_is_not_assumed_later_when_provider_predictions_change():
    result = choose(snapshot(600, 420))
    assert result['bus_order'] == 2 and result['remaining_seconds'] == 420


def test_eta_without_verified_message_basis_is_rejected():
    data = snapshot(420, 480)
    data['stops'][0]['buses'][0]['eta_basis'] = 'travel_time_minutes'
    result = choose(data)
    assert result['bus_order'] == 2 and result['excluded'][0]['reason'] == 'unverified_eta_basis'
