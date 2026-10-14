"""부분 응답이 현재 열차 선택으로 잘못 이어지지 않는 통제 시험."""
from copy import deepcopy
from datetime import datetime, timedelta

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from .test_subway_boardable_v1 import NOW, policy, snapshot


def source_for(payload, *, key='controlled-test-key', cache=None):
    calls = []
    checked = datetime.now(NOW.tzinfo) + timedelta(seconds=2)
    def transport(url, params):
        calls.append(url)
        return httpx.Response(200, json=deepcopy(payload), request=httpx.Request('GET', url))
    return SeoulSubwayArrival(service_key=key, transport=transport, cache=cache,
                             now=lambda: checked), calls, checked


def payload(total=1, rows=None):
    return {'errorMessage': {'code': 'INFO-000', 'total': total},
            'realtimeArrivalList': [{}] if rows is None else rows}


@pytest.mark.parametrize('key,end', [('controlled-test-key', 1000), ('sample', 5)])
def test_documented_maximum_is_requested_once_not_extra_pages(key, end):
    source, calls, _ = source_for(payload(), key=key)
    assert source.arrivals('서울') is not None
    assert len(calls) == 1 and f'/0/{end}/' in calls[0]


@pytest.mark.parametrize('total', [1, '1', '0001'])
def test_full_response_preserves_count_before_line_filter(total):
    source, _, _ = source_for(payload(total, [{'subwayId': '1001'}]))
    got = source.arrivals('서울', line='5호선')
    assert got['trains'] == []
    assert got['provider_total'] == 1 and got['response_row_count'] == 1
    assert got['coverage_complete'] is True


def test_partial_response_is_preserved_without_claiming_complete():
    source, _, _ = source_for(payload(22, [{}] * 20))
    got = source.arrivals('서울')
    assert len(got['trains']) == 20
    assert got['provider_total'] == 22 and got['response_row_count'] == 20
    assert got['coverage_complete'] is False


@pytest.mark.parametrize('value', [True, False, -1, '-1', 1.0, '1.0', '', None,
                                 [], {}, '²', '１', '9' * 5000])
def test_invalid_provider_total_is_not_cached_as_normal(value):
    source, _, _ = source_for(payload(value))
    assert source.arrivals('서울') is None
    assert source.misses['body_error'] == 1


def test_total_smaller_than_rows_is_provider_contradiction():
    source, _, _ = source_for(payload(0))
    assert source.arrivals('서울') is None


def test_compatible_root_and_nested_counts_agree():
    data = payload('1'); data['list_total_count'] = 1
    source, _, _ = source_for(data)
    assert source.arrivals('서울')['coverage_complete'] is True


def test_conflicting_root_and_nested_counts_are_rejected():
    data = payload(1); data['list_total_count'] = 2
    source, _, _ = source_for(data)
    assert source.arrivals('서울') is None


@pytest.mark.parametrize('data', [
    {'code': 'INFO-200'}, {'errorMessage': {'code': 'INFO-200'}},
    payload(0, []), {'list_total_count': '0', 'realtimeArrivalList': []},
])
def test_official_or_declared_zero_is_complete_empty(data):
    source, _, _ = source_for(data)
    got = source.arrivals('서울')
    assert got['trains'] == [] and got['provider_total'] == 0
    assert got['response_row_count'] == 0 and got['coverage_complete'] is True


def test_empty_code_with_positive_total_is_not_normal_empty():
    source, _, _ = source_for({'code': 'INFO-200', 'total': 1})
    assert source.arrivals('서울') is None


def test_missing_count_is_explicit_unknown_not_invented_complete():
    source, _, _ = source_for({'realtimeArrivalList': [{}]})
    got = source.arrivals('서울')
    assert got['provider_total'] is None and got['coverage_complete'] is None


@pytest.mark.parametrize('complete,reason', [(False, 'incomplete_arrivals'),
                                          (None, 'arrival_total_unknown')])
def test_partial_or_unknown_cannot_pick_even_an_otherwise_boardable_train(complete, reason):
    from app.domains.travel_ops.ports.data_sources.seoul_subway import select_boardable_arrival
    data = snapshot(); data['coverage_complete'] = complete
    got = select_boardable_arrival(data, **policy())
    assert got['status'] == 'unavailable' and got['reason'] == reason


def test_train_after_old_twenty_row_boundary_is_selected_from_full_request():
    from .test_subway_boardable_v1 import LINE, STATION, NEXT, TERMINAL
    checked = datetime.now(NOW.tzinfo) + timedelta(seconds=2)
    row = {'subwayId': LINE, 'statnId': STATION, 'statnTid': NEXT,
           'bstatnId': TERMINAL, 'btrainSttus': '일반', 'btrainNo': '5010',
           'barvlDt': 200, 'arvlCd': '99', 'recptnDt': checked.isoformat()}
    calls = []
    def transport(url, params):
        calls.append(url)
        end = int(url.split('/')[-2])
        rows = [{}] * 20 + [row]
        return httpx.Response(200, json=payload(21, rows[:end]), request=httpx.Request('GET', url))
    source = SeoulSubwayArrival(service_key='controlled-test-key', transport=transport, now=lambda: checked)
    got = source.boardable_arrival('서울', **policy(now=checked, ready_at=checked+timedelta(seconds=100)))
    assert got['status'] == 'predicted' and got['train_number'] == '5010'
    assert len(calls) == 1


def test_partial_source_result_reaches_model_revalidation_with_reason():
    from .mobility.test_subway_departure_v1 import scene, call
    from app.domains.travel_ops.ports.data_sources.seoul_subway import select_boardable_arrival
    rt, context = scene()
    def source(station, **kw):
        data = snapshot(); data['confirmed_at'] = kw['now'].isoformat()
        data['coverage_complete'] = False
        return select_boardable_arrival(data, max_age_seconds=30,
            max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2, **kw)
    got = call(rt, context, subway_arrival=source)
    assert got['status'] == 'model_revalidated'
    assert got['observations'][0]['reason'] == 'incomplete_arrivals'
