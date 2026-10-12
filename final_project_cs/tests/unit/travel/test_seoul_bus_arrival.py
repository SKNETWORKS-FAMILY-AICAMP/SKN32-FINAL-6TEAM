"""버스 도착정보의 시간 단위·방향 선택·인증 오류를 확인한다."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
from app.domains.travel_ops.ports.data_sources.seoul_bus import KST, SeoulBusArrival, message_eta_seconds

KEY = 'TEST_PRIVATE_KEY'
NOW = datetime(2026, 10, 8, 15, 10, tzinfo=KST)


def row(sequence=5, **changes):
    return {'busRouteId': '100100118', 'stId': '111000181', 'staOrd': str(sequence),
            'rtNm': '753', 'stNm': '여행 출발 정류장', 'dir': '서울역',
            'mkTm': '2026-10-08 15:09:30.0', 'arrmsg1': '3분 31초 후 (2번째 전)',
            'arrmsg2': '출발대기', 'traTime1': '8', 'isLast1': '0', 'full1': '1', **changes}


def source(rows, *, header='0', seen=None, **kwargs):
    def transport(url, params):
        if seen is not None:
            seen.append((url, params))
        return httpx.Response(200, json={'msgHeader': {'headerCd': header},
                                        'msgBody': {'itemList': rows}})
    return SeoulBusArrival(service_key=KEY, transport=transport, now=lambda: NOW, **kwargs)


@pytest.mark.parametrize('message,seconds', [
    ('3분31초 후', 211), ('31초 후 (2번째 전)', 31), ('0초 후', 0),
    ('3분 후', 180), ('4분38초후[2번째 전]', 278), ('2분후[1번째 전]', 120),
    ('출발대기', None), ('운행종료', None),
    ('곧 도착', None), ('2번째 전', None), ('', None),
])
def test_provider_message_eta(message, seconds):
    assert message_eta_seconds(message) == seconds


def test_units_observation_time_and_request_parameter():
    seen = []
    got = source([row()], seen=seen).arrivals('100100118', stop_sequence=5)
    assert seen[0][1]['serviceKey'] == KEY and 'ServiceKey' not in seen[0][1]
    st = got['stops'][0]
    assert st['received_age_seconds'] == 30
    assert st['buses'][0]['eta_seconds'] == 211
    assert st['buses'][0]['travel_time_minutes'] == 8
    assert st['buses'][1]['eta_seconds'] is None
    assert st['buses'][1]['is_last'] is None
    assert 'raw' not in st and got['source'] == 'seoul_bus_arrival'


def test_loop_stop_requires_sequence_to_select_one_direction():
    src = source([row(5), row(90)])
    got = src.arrivals('100100118', stop_id='111000181')
    assert len(got['stops']) == 2 and got['ambiguous_stop']
    got = src.arrivals('100100118', stop_id='111000181', stop_sequence=90)
    assert [s['stop_sequence'] for s in got['stops']] == [90] and not got['ambiguous_stop']


def test_auth_failure_is_not_success_or_cached(caplog):
    assert source([], header='7').arrivals('100100118') is None
    def transport(url, params):
        return httpx.Response(401, text=f'invalid key {KEY}')
    src = SeoulBusArrival(service_key=KEY, transport=transport)
    assert src.arrivals('100100118') is None and KEY not in caplog.text


def test_empty_success_and_wrong_shapes():
    assert source([]).arrivals('100100118')['stops'] == []
    assert source('bad').arrivals('100100118') is None
    assert source(row()).arrivals('100100118')['stops'][0]['stop_sequence'] == 5


def test_route_cache_shared_across_stop_filters_and_expires_in_30_seconds():
    elapsed = [0]
    cache = ResponseCache(300, clock=lambda: elapsed[0], wall=lambda: NOW)
    seen = []
    src = source([row(5), row(90)], seen=seen, cache=cache)
    first = src.arrivals('100100118', stop_sequence=5)
    elapsed[0] = 29
    src._now = lambda: NOW + timedelta(seconds=29)
    second = src.arrivals('100100118', stop_sequence=90)
    assert len(seen) == 1 and first['confirmed_at'] == second['confirmed_at']
    assert second['stops'][0]['received_age_seconds'] == 59
    elapsed[0] = 30
    src.arrivals('100100118', stop_sequence=5)
    assert len(seen) == 2


def test_common_key_assembles_bus_source(monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings, 'get_guardrails', lambda: SimpleNamespace(get=lambda _: None))
    sources = build_travel_sources(SimpleNamespace(data_go_kr_key=KEY, weather_provider='open_meteo'))
    assert sources.bus_arrival is not None and sources.bus_arrival._key == KEY
