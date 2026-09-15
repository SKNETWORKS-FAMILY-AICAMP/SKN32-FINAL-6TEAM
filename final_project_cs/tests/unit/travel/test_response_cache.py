# -*- coding: utf-8 -*-
"""응답 캐시 — 같은 요청을 다시 내보내지 않되, **확인 시각을 속이지 않는다.**

☆2026-09-14 실측: 감시 루프 한 틱이 항목 여럿을 점검하자 특보·대기질·지진이 같은
  요청을 연달아 보냈고, 둘째부터 속도 제한에 걸려 「모름」→ 치명이 됐다.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.infrastructure.travel.base import TravelSource
from app.infrastructure.travel.cache import ResponseCache
from app.infrastructure.travel.ratelimit import RateLimiter, interval_for


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Probe(TravelSource):
    name = "src"

    def read(self, **params):
        payload = self._fetch_json("https://x", params)
        return None if payload is None else self.stamp(payload, source=self.name)


def _probe(cache, *, status=200, limiter=None):
    calls = []

    def transport(url, params):
        calls.append(dict(params))
        return httpx.Response(status, json={"n": len(calls)}, request=httpx.Request("GET", url))
    return _Probe(transport=transport, cache=cache, limiter=limiter), calls


def test_the_same_request_is_served_from_the_cache_without_going_out():
    probe, calls = _probe(ResponseCache(ttl_seconds=300))
    first, second = probe.read(a=1), probe.read(a=1)
    assert len(calls) == 1 and second["n"] == first["n"]


def test_a_cached_value_keeps_its_original_confirmation_time():
    """★재사용한 값에 「지금 확인」을 찍으면 확인 시각을 속인다(v10 §4-D)."""
    fetched = datetime(2026, 9, 14, 3, 0, tzinfo=UTC)
    cache = ResponseCache(ttl_seconds=300, wall=lambda: fetched)
    probe, _ = _probe(cache)
    first = probe.read(a=1)
    second = probe.read(a=1)
    assert "from_cache" not in first
    assert second["from_cache"] is True
    assert second["confirmed_at"] == first["confirmed_at"]


def test_different_params_go_out_separately():
    probe, calls = _probe(ResponseCache(ttl_seconds=300))
    probe.read(a=1)
    probe.read(a=2)
    assert len(calls) == 2


def test_an_expired_entry_goes_out_again():
    clock = _Clock()
    probe, calls = _probe(ResponseCache(ttl_seconds=300, clock=clock))
    probe.read(a=1)
    clock.now = 301
    probe.read(a=1)
    assert len(calls) == 2


def test_failures_are_not_cached():
    """★실패를 재사용하면 공급자가 살아나도 몇 분 동안 계속 「모름」이다."""
    probe, calls = _probe(ResponseCache(ttl_seconds=300), status=500)
    assert probe.read(a=1) is None and probe.read(a=1) is None
    assert len(calls) == 2


def test_a_cache_hit_does_not_spend_the_rate_limit():
    """★재사용은 바깥으로 안 나가니 한도를 안 쓴다 — 캐시를 제한기보다 먼저 본다."""
    limiter = RateLimiter(intervals={"src": interval_for(1_000)}, max_wait_seconds=0.0)
    probe, calls = _probe(ResponseCache(ttl_seconds=300), limiter=limiter)
    for _ in range(5):
        assert probe.read(a=1) is not None
    assert len(calls) == 1 and limiter.refusals == {}


def test_a_returned_value_is_a_copy():
    probe, _ = _probe(ResponseCache(ttl_seconds=300))
    probe.read(a=1)["n"] = "고쳐 씀"
    assert probe.read(a=1)["n"] == 1


@pytest.mark.parametrize("ttl", [0, -1])
def test_zero_ttl_turns_the_cache_off(ttl):
    probe, calls = _probe(ResponseCache(ttl_seconds=ttl))
    probe.read(a=1)
    probe.read(a=1)
    assert len(calls) == 2
