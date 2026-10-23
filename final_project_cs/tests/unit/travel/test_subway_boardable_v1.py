"""통제 응답의 현재 승차 예측. 실탑승·독립 ETA 정확도 시험이 아니다."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
import httpx

from app.domains.travel_ops.ports.data_sources import seoul_subway as subway

NOW = datetime.fromisoformat('2026-10-09T10:00:00+09:00')
LINE, STATION, NEXT, TARGET, TERMINAL = '1005', '1005000522', '1005000523', '1005000524', '1005000530'
PATH = {'train_status': '일반', 'path_station_ids': [STATION, NEXT, TARGET, TERMINAL]}


def train(**changes):
    return dict(line_id=LINE, station_id=STATION, next_station_id=NEXT,
                terminal_station_id=TERMINAL, train_status='일반', train_number='5010',
                eta_seconds=200, eta_status='valid', arrival_code='99',
                received_at=(NOW - timedelta(seconds=20)).replace(tzinfo=None).isoformat(), **changes)


def snapshot(rows=None):
    return {'kind': 'subway_arrival', 'source': 'controlled/arrival',
            'confirmed_at': (NOW - timedelta(seconds=5)).isoformat(),
            'trains': [train()] if rows is None else rows}


def policy(**changes):
    result = dict(line_id=LINE, station_id=STATION, target_station_id=TARGET,
                  allowed_services=[deepcopy(PATH)], now=NOW, ready_at=NOW + timedelta(seconds=100),
                  max_age_seconds=30, max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2)
    result.update(changes)
    return result


def select(data=None, **changes):
    function = getattr(subway, 'select_boardable_arrival', None)
    assert function is not None, '지하철의 접근 이후 선택기가 없다'
    return function(snapshot() if data is None else data, **policy(**changes))


def test_provider_generation_time_is_eta_origin_and_cache_age_not_subtracted_twice():
    original = snapshot()
    kept = deepcopy(original)
    got = select(original)
    assert got['status'] == 'predicted', got
    assert got['arrival_at'] == (NOW + timedelta(seconds=180)).isoformat()
    assert got['remaining_seconds'] == 180 and got['wait_after_access_seconds'] == 80
    assert got['provider_age_seconds'] == 20 and got['observation_age_seconds'] == 5
    assert got['train_number'] == '5010' and got['target_station_id'] == TARGET
    assert original == kept


def test_missed_first_train_selects_second_without_using_old_age_summary():
    first = train()
    first.update(eta_seconds=90, received_age_seconds=-999)
    second = train()
    second.update(eta_seconds=240, train_number='5011')
    got = select(snapshot([first, second]))
    assert got['status'] == 'predicted' and got['train_number'] == '5011'
    assert got['remaining_seconds'] == 220
    assert got['excluded'][0]['reason'] == 'arrives_before_ready'


@pytest.mark.parametrize('field,value,reason', [
    ('line_id', '1002', 'boarding_identity_mismatch'),
    ('station_id', '1005000500', 'boarding_identity_mismatch'),
    ('next_station_id', '1005000521', 'service_path_mismatch'),
    ('terminal_station_id', NEXT, 'service_path_mismatch'),
    ('train_status', '급행', 'service_path_mismatch'),
    ('train_status', 'ITX', 'service_path_mismatch'),
    ('train_number', None, 'train_identity_missing'),
    ('arrival_code', '2', 'departed_or_unknown_state'),
    ('arrival_code', None, 'departed_or_unknown_state'),
    ('arrival_code', True, 'departed_or_unknown_state'),
    ('received_at', 'bad', 'invalid_provider_received_at'),
    ('eta_seconds', True, 'no_numeric_eta'),
    ('eta_seconds', -1, 'no_numeric_eta'),
    ('eta_seconds', float('inf'), 'no_numeric_eta'),
    ('eta_seconds', 10**100, 'invalid_arrival_time'),
    ('eta_status', 'missing', 'no_numeric_eta'),
])
def test_unrelated_or_invalid_train_is_not_selected(field, value, reason):
    row = train()
    row[field] = value
    got = select(snapshot([row]))
    assert got['status'] == 'no_boardable_prediction'
    assert got['excluded'][0]['reason'] == reason


@pytest.mark.parametrize('field,value,reason', [
    ('line_id', True, 'boarding_identity_invalid'),
    ('station_id', 'bad', 'boarding_identity_invalid'),
    ('target_station_id', STATION, 'boarding_identity_invalid'),
    ('max_age_seconds', 0, 'invalid_freshness_policy'),
    ('max_provider_age_seconds', float('nan'), 'invalid_freshness_policy'),
    ('max_provider_clock_ahead_seconds', -1, 'invalid_freshness_policy'),
    ('now', NOW.replace(tzinfo=None), 'timezone_required'),
    ('ready_at', NOW - timedelta(seconds=1), 'invalid_ready_at'),
    ('allowed_services', [], 'service_path_invalid'),
    ('allowed_services', [{'train_status': '급행', 'path_station_ids': PATH['path_station_ids']}], 'service_path_invalid'),
    ('allowed_services', [{'train_status': '일반', 'path_station_ids': [STATION, NEXT, STATION, TARGET]}], 'service_path_invalid'),
    ('allowed_services', [{'train_status': '일반', 'path_station_ids': [STATION, NEXT, TERMINAL]}], 'service_path_invalid'),
])
def test_invalid_caller_inputs_are_explicit_and_do_not_mutate(field, value, reason):
    got = select(**{field: value})
    assert got['status'] == 'unavailable' and got['reason'] == reason


@pytest.mark.parametrize('delta,status,reason', [(-3, 'no_boardable_prediction', 'provider_clock_in_future'),
                                               (91, 'no_boardable_prediction', 'provider_refresh_required')])
def test_provider_freshness_is_separate_from_recent_http_confirmation(delta, status, reason):
    row = train()
    row['received_at'] = (NOW - timedelta(seconds=delta)).isoformat()
    got = select(snapshot([row]))
    assert got['status'] == status and got['excluded'][0]['reason'] == reason


@pytest.mark.parametrize('delta,status,reason', [(30, 'stale', 'refresh_required'),
                                               (-1, 'unavailable', 'confirmation_in_future')])
def test_cache_age_boundary_and_future_confirmation(delta, status, reason):
    data = snapshot()
    data['confirmed_at'] = (NOW - timedelta(seconds=delta)).isoformat()
    got = select(data)
    assert got['status'] == status and got['reason'] == reason


def test_duplicate_train_number_cannot_invent_a_choice():
    got = select(snapshot([train(), train()]))
    assert got['status'] == 'no_boardable_prediction'
    assert [x['reason'] for x in got['excluded']] == ['duplicate_train_identity'] * 2


def test_zero_eta_needs_station_arrival_state_and_zero_access():
    row = train()
    row.update(eta_seconds=0, arrival_code='0', received_at=NOW.isoformat())
    assert select(snapshot([row]), ready_at=NOW)['status'] == 'predicted'
    row['arrival_code'] = '99'
    got = select(snapshot([row]), ready_at=NOW)
    assert got['excluded'][0]['reason'] == 'zero_eta_without_arrival_state'


def test_no_train_after_ready_is_not_no_service_claim():
    got = select(snapshot([]))
    assert got['status'] == 'no_boardable_prediction' and got['reason'] == 'no_vehicle_after_ready'


def test_query_completion_preserves_whole_access_and_does_not_shift_provider_eta():
    source = subway.SeoulSubwayArrival(service_key='controlled-test-key', now=lambda: NOW + timedelta(seconds=1))
    calls = []
    def arrivals(station, *, line=None):
        calls.append((station, line))
        row = train()
        row.update(received_at=NOW.isoformat(), eta_seconds=150)
        return snapshot([row])
    source.arrivals = arrivals
    function = getattr(source, 'boardable_arrival', None)
    assert function is not None, '소스 조회→현재 시각 선택이 없다'
    got = function('양평', **policy())
    assert calls == [('양평', None)]
    assert got['evaluated_at'] == (NOW + timedelta(seconds=1)).isoformat()
    assert got['ready_at'] == (NOW + timedelta(seconds=160)).isoformat()
    assert got['status'] == 'no_boardable_prediction'


def test_invalid_selection_input_never_spends_an_http_call():
    source = subway.SeoulSubwayArrival(service_key='controlled-test-key', now=lambda: NOW)
    source.arrivals = lambda *a, **kw: pytest.fail('유효하지 않은 입력은 API를 부르면 안 됨')
    function = getattr(source, 'boardable_arrival', None)
    assert function is not None, '입력 선검사가 없다'
    assert function('양평', **policy(line_id=True))['reason'] == 'boarding_identity_invalid'


@pytest.mark.parametrize('data,reason', [
    (None, 'invalid_snapshot'), ({}, 'invalid_snapshot'),
    (dict(kind='bus_arrival', source='wrong'), 'invalid_snapshot'),
    (dict(snapshot(), source=None), 'invalid_snapshot'),
    (dict(snapshot(), confirmed_at='bad'), 'invalid_confirmed_at'),
    (dict(snapshot(), confirmed_at=NOW.replace(tzinfo=None).isoformat()), 'timezone_required'),
    (dict(snapshot(), trains=None), 'invalid_trains'),
    (dict(snapshot(), trains=[None]), 'invalid_trains'),
])
def test_invalid_snapshot_is_not_an_empty_service(data, reason):
    got = subway.select_boardable_arrival(data, **policy())
    assert got['status'] == 'unavailable' and got['reason'] == reason


@pytest.mark.parametrize('path', [None, {}, ['1'], [STATION, True, TARGET], [NEXT, STATION, TARGET]])
def test_malformed_path_is_not_invented(path):
    assert select(allowed_services=[{'train_status': '일반', 'path_station_ids': path}])['reason'] == 'service_path_invalid'


@pytest.mark.parametrize('value', [float('inf'), True, 10**1000])
def test_unusable_freshness_policy_never_overflows(value):
    assert select(max_age_seconds=value)['reason'] == 'invalid_freshness_policy'


def test_ambiguous_service_identity_is_refused():
    other = dict(PATH, path_station_ids=[STATION, NEXT, '1005000550', TARGET, TERMINAL])
    assert select(allowed_services=[PATH, other])['reason'] == 'service_path_invalid'


@pytest.mark.parametrize('field,value', [('next_station_id', {}), ('train_status', []), ('train_number', [])])
def test_malformed_train_identity_does_not_crash(field, value):
    row = train()
    row[field] = value
    assert select(snapshot([row]))['status'] == 'no_boardable_prediction'


@pytest.mark.parametrize('evaluated', [NOW - timedelta(seconds=1), NOW.replace(tzinfo=None), 'bad'])
def test_invalid_query_clock_is_explicit(evaluated):
    source = subway.SeoulSubwayArrival(service_key='controlled-test-key', now=lambda: evaluated)
    source.arrivals = lambda *a, **kw: snapshot()
    got = source.boardable_arrival('양평', **policy())
    assert got['status'] == 'unavailable' and got['reason'] == 'invalid_evaluation_clock'


def test_normalized_http_response_flows_through_source_to_selection():
    checked = datetime.now(NOW.tzinfo)
    received = checked - timedelta(seconds=20)
    calls = []
    def transport(url, params):
        calls.append(True)
        row = {'subwayId': LINE, 'statnId': STATION, 'statnTid': NEXT, 'bstatnId': TERMINAL,
               'btrainSttus': '일반', 'btrainNo': '5010', 'barvlDt': '200', 'arvlCd': '99',
               'recptnDt': received.isoformat()}
        return httpx.Response(200, json={'errorMessage': {'code': 'INFO-000', 'total': 1},
                                        'realtimeArrivalList': [row]}, request=httpx.Request('GET', url))
    source = subway.SeoulSubwayArrival(service_key='controlled-test-key', transport=transport,
                                        now=lambda: checked + timedelta(seconds=2))
    got = source.boardable_arrival('양평', **policy(now=checked, ready_at=checked + timedelta(seconds=100)))
    assert len(calls) == 1 and got['status'] == 'predicted', got
    assert got['arrival_at'] == (received + timedelta(seconds=200)).isoformat()
    assert got['remaining_seconds'] == 178
