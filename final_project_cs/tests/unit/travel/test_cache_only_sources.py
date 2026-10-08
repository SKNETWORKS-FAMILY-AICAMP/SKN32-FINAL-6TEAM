# -*- coding: utf-8 -*-
"""캐시만 읽는 소스 — `CacheOnlyLimiter`. `[2026-10-06 사용자 요청 — MCP 일정 위험 점검이 하루 한도를 깎지 않게]`

★지키려는 것
 ①`CacheOnlyLimiter` 로 만든 소스는 **바깥으로 한 번도 안 나간다** — 캐시에 있으면 값을 주고(확인 시각은 처음 받아 온 때), 없으면 `None`(모름). 한도 줄 · 실패 수에 안 센다. 경고 로그도 안 남긴다.
 ②실제 조립: `build_travel_sources(cache_only=True)` 의 모든 소스가 닫힌 문을 쓴다. 낮은 우선순위 몫(`CallBudget.share`)은 DB 시험(`tests/integration/db/test_source_budget_db.py`)이 본다.

재현:

    python -m pytest tests/unit/travel/test_cache_only_sources.py -v
"""
from __future__ import annotations

import logging

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.base import TravelSource
from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
from app.domains.travel_ops.ports.data_sources.ratelimit import CacheOnly, CacheOnlyLimiter, RateLimited


class Probe(TravelSource):
    name = "probe"

    def read(self):
        return self._fetch_json("https://example.test/x", {"a": 1})


def _transport(calls):
    def get(url, params):
        calls.append((url, params))
        return httpx.Response(200, json={"ok": True})
    return get


def test_a_cache_only_source_never_goes_out_and_misses_quietly(caplog):
    calls: list = []
    source = Probe(transport=_transport(calls), limiter=CacheOnlyLimiter(), cache=ResponseCache(ttl_seconds=60))
    with caplog.at_level(logging.DEBUG):
        assert source.read() is None                                                           # 캐시가 비었다 → 모름
    assert calls == [] and source.misses["cache_only"] == 1
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]                     # ① 경고가 아니다


def test_a_cache_only_source_serves_what_the_watch_already_collected_with_the_original_time():
    cache = ResponseCache(ttl_seconds=60)
    calls: list = []
    warm = Probe(transport=_transport(calls), cache=cache)                                      # 감시가 먼저 받아 온다(제한기 없음 = 시험)
    assert warm.read() == {"ok": True} and len(calls) == 1
    only = Probe(transport=_transport(calls), limiter=CacheOnlyLimiter(), cache=cache)
    assert only.read() == {"ok": True} and len(calls) == 1                                      # 바깥으로 안 나갔다
    stamped = only.stamp({"v": 1}, source="probe")
    assert stamped["from_cache"] is True and stamped["confirmed_at"]                           # 확인 시각은 처음 받아 온 때


def test_the_cache_only_door_is_a_normal_rate_limited_branch():
    with pytest.raises(CacheOnly) as caught:
        CacheOnlyLimiter().acquire("kma")
    assert isinstance(caught.value, RateLimited) and caught.value.reason == "cache_only" and caught.value.wait_seconds == 0.0


# ── 실제 조립 ─────────────────────────────────────────────────────
def test_the_cache_only_assembly_closes_every_door(monkeypatch):
    from app.core import settings as settings_module
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources

    sources = build_travel_sources(settings_module.get_settings(), cache_only=True)
    assert isinstance(sources.limiter, CacheOnlyLimiter)
    with pytest.raises(CacheOnly):
        sources.limiter.acquire("kma")
    low = build_travel_sources(settings_module.get_settings(), low_priority_share=0.5)
    budgeted = getattr(low.limiter, "_budget", None)                                              # 한도를 아는 소스가 있는 환경이면 DB 예산이 얹힌다
    if budgeted is not None:
        assert budgeted.share == 0.5 and low.limiter._on_db_error == "refuse"                     # 몫 · DB 를 못 읽으면 안 부른다
    normal = build_travel_sources(settings_module.get_settings())
    assert getattr(getattr(normal.limiter, "_budget", None), "share", 1.0) == 1.0                  # 일반 조립은 몫이 없다


def test_the_whole_check_over_the_cache_only_assembly_makes_no_outbound_call_at_all(monkeypatch):
    """`[검토 반영]` 한도 걱정이 규약에만 기대지 않게 — 실제 어댑터(키가 있는 것 전부)로 6종 점검을 돌려도 HTTP · urllib 이 한 번도 불리지 않는다."""
    import urllib.request
    from datetime import UTC, datetime

    from app.core import settings as settings_module
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck

    calls = []

    def forbid(*args, **kwargs):
        calls.append(args[:1])
        raise AssertionError("바깥으로 나갔다")

    monkeypatch.setattr(httpx, "get", forbid)
    monkeypatch.setattr(httpx.Client, "send", forbid)
    monkeypatch.setattr(urllib.request, "urlopen", forbid)
    sources = build_travel_sources(settings_module.get_settings(), cache_only=True)
    report = DisruptionCheck(sources).check(place={"place_id": "x", "name": "시험", "latitude": 37.57, "longitude": 126.98, "weather_sensitive": True},
                                            starts_at=datetime.now(UTC))
    assert calls == []
    assert len(report["checks"]) >= 6                                                         # 6종 점검이 실제로 돌았다(캐시가 비어 모름 · 미연결로 끝나도)
