"""실제 메모리 보관기를 사용한 통제 HTTP 응답 시험. 실제 운행 관측이 아니다."""
from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival


BAD = [
    {}, {'errorMessage': {'code': 'INFO-000'}},
    {'code': 'INFO-000', 'realtimeArrivalList': None}, {'realtimeArrivalList': None},
    {'realtimeArrivalList': {}}, {'realtimeArrivalList': 'not a list'},
    {'realtimeArrivalList': [None]}, {'realtimeArrivalList': [{'barvlDt': 180}, 'bad']},
    {'code': 'INFO-200', 'realtimeArrivalList': [{'barvlDt': 180}]},
    {'errorMessage': {'code': 'INFO-200'}, 'realtimeArrivalList': [{'barvlDt': 180}]},
]
GOOD = {'errorMessage': {'code': 'INFO-000'}, 'realtimeArrivalList': [{'barvlDt': 0}]}
EMPTY = [
    {'realtimeArrivalList': []}, {'errorMessage': {'code': 'INFO-000'}, 'realtimeArrivalList': []},
    *[dict(code='INFO-200', **rows) for rows in ({}, {'realtimeArrivalList': None}, {'realtimeArrivalList': []})],
    *[dict(errorMessage={'code': 'INFO-200'}, **rows)
      for rows in ({}, {'realtimeArrivalList': None}, {'realtimeArrivalList': []})],
]


class Budget:
    def __init__(self):
        self.calls = 0
        self.failures = 0

    def acquire(self, source):
        self.calls += 1

    def record_failure(self, source):
        self.failures += 1


def source(responses):
    seen = []
    remaining = iter(responses)

    def transport(url, params):
        seen.append(url)
        return httpx.Response(200, json=deepcopy(next(remaining)), request=httpx.Request('GET', url))

    cache = ResponseCache(ttl_seconds=300, clock=lambda: 0)
    budget = Budget()
    src = SeoulSubwayArrival(service_key='controlled-test-key', transport=transport,
                              cache=cache, limiter=budget)
    return src, cache, budget, seen


@pytest.mark.parametrize('payload', BAD)
def test_bad_response_is_failure_and_recovery_is_not_hidden_by_cache(payload):
    src, cache, budget, seen = source([payload, GOOD])
    assert src.arrivals('서울') is None
    assert src.misses['body_error'] == 1
    assert cache.stores == 0 and budget.calls == 1 and budget.failures == 1
    recovered = src.arrivals('서울')
    assert recovered['trains'][0]['eta_seconds'] == 0
    assert len(seen) == 2 and cache.stores == 1 and budget.calls == 2 and budget.failures == 1


@pytest.mark.parametrize('payload', BAD)
def test_preexisting_bad_cache_is_rejected_without_a_new_provider_call(payload):
    src, cache, budget, seen = source([GOOD])
    src.arrivals('서울')
    key = next(iter(cache._items))
    cache.put(key, payload, fetched_at=datetime(2026, 10, 9, 0, tzinfo=UTC))
    got = src.arrivals('서울')
    assert got is None
    assert src.misses['malformed_arrivals'] == 1
    assert len(seen) == 1 and budget.calls == 1 and budget.failures == 0


@pytest.mark.parametrize('payload', EMPTY)
def test_real_empty_contract_is_preserved_and_can_be_reused(payload):
    src, cache, budget, seen = source([payload])
    first = src.arrivals('서울')
    second = src.arrivals('서울')
    assert first['trains'] == second['trains'] == []
    assert second['from_cache'] is True and first['confirmed_at'] == second['confirmed_at']
    assert len(seen) == budget.calls == cache.stores == 1
    assert budget.failures == 0 and not src.misses
