"""실제 어댑터의 조회·캐시·선택 연결. HTTP 응답만 주입하며 외부 API를 호출하지 않는다."""
from datetime import datetime, timedelta

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
from app.domains.travel_ops.ports.data_sources.seoul_bus import SeoulBusArrival
from .test_bus_boardable_arrival_v1 import NOW


@pytest.fixture(autouse=True)
def response_receive_clock(monkeypatch):
    # ResponseCache.wall은 _remember가 명시한 실제 수신시각을 덮지 않는다.
    # 공급·소비·최초 수신 시계를 모두 같은 고정 실험 시각에 맞춘다.
    from app.domains.travel_ops.ports.data_sources import base
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
    monkeypatch.setattr(base, 'datetime', FixedDateTime)


def make_source(*, provider_age=8, header='0', full=False):
    elapsed = [0]
    seen = []
    received = (NOW - timedelta(seconds=provider_age)).replace(tzinfo=None).isoformat(' ')
    def row(seq, stop):
        return {'busRouteId': '100', 'stId': stop, 'staOrd': str(seq), 'mkTm': received,
                'stNm': '여행 출발 정류장', 'rtNm': '시내 이동', 'dir': '서울역',
                'arrmsg1': '3분 후', 'arrmsg2': '7분 후', 'full1': '1' if full else '0',
                'full2': '0', 'isLast1': '0', 'isLast2': '1'}
    def transport(url, params):
        seen.append(params.copy())
        return httpx.Response(200, json={'msgHeader': {'headerCd': header},
            'msgBody': {'itemList': [row(5, '101'), row(90, '101'), row(6, '102')]}})
    cache = ResponseCache(300, clock=lambda: elapsed[0], wall=lambda: NOW + timedelta(seconds=elapsed[0]))
    src = SeoulBusArrival(service_key='TEST_PRIVATE_KEY', transport=transport, cache=cache,
                          now=lambda: NOW + timedelta(seconds=elapsed[0]))
    return src, elapsed, seen


def read(src, *, now=NOW, stop='101', seq=5, ready=360, **changes):
    params = dict(stop_id=stop, stop_sequence=seq, now=now,
                  ready_at=now + timedelta(seconds=ready), max_age_seconds=30,
                  max_provider_age_seconds=90, max_provider_clock_ahead_seconds=0)
    params.update(changes)
    return src.boardable_arrival('100', **params)


def test_adapter_queries_exact_stop_and_selects_after_access():
    src, _, seen = make_source()
    got = read(src)
    assert got['status'] == 'predicted' and got['bus_order'] == 2
    assert got['stop_id'] == '101' and got['stop_sequence'] == 5
    assert got['remaining_seconds'] == 420 and got['wait_after_access_seconds'] == 60
    assert got['is_last'] is True and len(seen) == 1


def test_second_stop_and_loop_sequence_share_one_route_response():
    src, elapsed, seen = make_source()
    first = read(src)
    elapsed[0] = 20
    second = read(src, now=NOW + timedelta(seconds=20), stop='102', seq=6)
    loop = read(src, now=NOW + timedelta(seconds=20), seq=90)
    assert len(seen) == 1 and first['confirmed_at'] == second['confirmed_at'] == loop['confirmed_at']
    assert second['remaining_seconds'] == 400 and loop['stop_sequence'] == 90
    assert second['provider_age_seconds'] == 28


def test_fresh_http_response_does_not_refresh_old_provider_data():
    src, _, seen = make_source(provider_age=1200)
    got = read(src)
    assert len(seen) == 1 and got['status'] == 'stale'
    assert got['reason'] == 'provider_refresh_required' and got['provider_age_seconds'] == 1200
    assert 'arrival_at' not in got


def test_missing_source_and_provider_auth_failure_have_no_boardable_result():
    src, _, seen = make_source(header='7')
    got = read(src)
    assert len(seen) == 1 and got['status'] == 'unavailable'
    assert 'remaining_seconds' not in got
    empty = SeoulBusArrival(service_key='')
    assert read(empty)['status'] == 'unavailable'


@pytest.mark.parametrize('changes', [
    {'seq': True}, {'seq': 0}, {'seq': 5.0}, {'stop': ''}, {'ready': -1},
    {'now': NOW.replace(tzinfo=None)}, {'max_provider_age_seconds': float('nan')},
    {'max_provider_clock_ahead_seconds': -1}, {'max_age_seconds': 0},
])
def test_invalid_input_does_not_spend_a_source_call(changes):
    src, _, seen = make_source()
    assert read(src, **changes)['status'] == 'unavailable'
    assert seen == []
