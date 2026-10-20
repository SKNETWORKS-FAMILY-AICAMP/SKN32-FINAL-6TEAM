"""공휴일 실제 응답 뒤 발생한 캐시 충돌 회귀 시험."""
from datetime import date

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
from app.domains.travel_ops.ports.data_sources.holiday import HolidaySource
from app.domains.travel_ops.ports.data_sources.ratelimit import CacheOnlyLimiter


def response(items):
    return httpx.Response(200, json={"response": {"header": {"resultCode": "00"},
                                                "body": {"items": items}}})


def test_two_dates_in_the_month_use_one_response_with_the_injected_http_cache():
    calls = []
    cache = ResponseCache(300)

    def get(url, params):
        calls.append(params)
        return response({"item": {"locdate": 20261009, "dateName": "한글날"}})

    source = HolidaySource(service_key="unit-key", transport=get, cache=cache)
    holiday = source.is_holiday(date(2026, 10, 9))
    ordinary = source.is_holiday(date(2026, 10, 10))
    assert holiday["is_holiday"] is True and holiday["holiday_name"] == "한글날"
    assert ordinary["is_holiday"] is False and ordinary["holiday_name"] is None
    assert len(calls) == 1 and cache.stores == 1


def test_a_new_source_reads_the_shared_http_response_without_using_the_network():
    cache = ResponseCache(300)
    first = HolidaySource(service_key="unit-key", cache=cache,
                          transport=lambda *args: response({"item": {"locdate": 20261009, "dateName": "한글날"}}))
    initial = first.is_holiday(date(2026, 10, 9))

    def forbid(*args):
        pytest.fail("캐시 전용 조회가 외부를 호출했습니다")

    second = HolidaySource(service_key="unit-key", cache=cache, transport=forbid,
                           limiter=CacheOnlyLimiter())
    reused = second.is_holiday(date(2026, 10, 9))
    assert reused["holiday_name"] == initial["holiday_name"]
    assert reused["from_cache"] is True and reused["confirmed_at"] == initial["confirmed_at"]


def test_a_month_without_holidays_is_a_valid_negative_answer():
    source = HolidaySource(service_key="unit-key", cache=ResponseCache(300),
                           transport=lambda *args: response(""))
    assert source.is_holiday(date(2026, 11, 2))["is_holiday"] is False


@pytest.mark.parametrize("failure", ["timeout", "http", "body"])
def test_provider_failure_does_not_invent_a_non_holiday(failure):
    def get(*args):
        if failure == "timeout":
            raise httpx.ReadTimeout("unit timeout")
        if failure == "http":
            return httpx.Response(503)
        return httpx.Response(200, json={"response": {"header": {"resultCode": "30"}}})

    cache = ResponseCache(300)
    source = HolidaySource(service_key="unit-key", cache=cache, transport=get)
    assert source.is_holiday(date(2026, 10, 9)) is None
    assert sum(source.misses.values()) == 1 and cache.stores == 0


def test_a_cold_cache_only_source_never_calls_the_provider():
    def forbid(*args):
        pytest.fail("캐시 전용 조회가 외부를 호출했습니다")

    source = HolidaySource(service_key="unit-key", cache=ResponseCache(300),
                           limiter=CacheOnlyLimiter(), transport=forbid)
    assert source.is_holiday(date(2026, 10, 9)) is None
    assert source.misses["cache_only"] == 1
