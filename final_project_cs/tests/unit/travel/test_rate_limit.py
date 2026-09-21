# -*- coding: utf-8 -*-
"""호출 속도 제한 — **하루 한도를 하루에 걸쳐 쓴다.**

★왜 (2026-09-10 사용자 지시). 시험한다고 빨리 두들기면 그날치 한도를 태우고
  차단당한다. 공공데이터포털 개발계정은 서비스에 따라 500~10,000/일이라
  금방 넘긴다.

★시계와 잠을 **주입**해서 시험한다. 실제로 자면 시험이 하루 걸린다.
"""
from __future__ import annotations

import httpx
import pytest

from app.infrastructure.travel.base import TravelSource
from app.infrastructure.travel.ratelimit import (
    RateLimited, RateLimiter, SECONDS_PER_DAY, interval_for,
)


class _Clock:
    """수동 시계. `advance()` 로만 흐른다."""

    def __init__(self) -> None:
        self.now, self.slept = 0.0, []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _limiter(per_day: int, *, max_wait: float = 5.0) -> tuple[RateLimiter, _Clock]:
    clock = _Clock()
    return RateLimiter(intervals={"src": interval_for(per_day)},
                       max_wait_seconds=max_wait,
                       clock=clock, sleep=clock.sleep), clock


# ── 환산 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("per_day,seconds", [
    (10_000, 8.64), (1_000, 86.4), (500, 172.8), (86_400, 1.0),
])
def test_a_daily_quota_becomes_an_even_interval(per_day, seconds):
    assert interval_for(per_day) == pytest.approx(seconds)


def test_an_interval_times_the_quota_is_exactly_one_day():
    """★환산이 맞으면 하루에 정확히 한도만큼 나간다."""
    for per_day in (500, 1_000, 10_000):
        assert interval_for(per_day) * per_day == pytest.approx(SECONDS_PER_DAY)


@pytest.mark.parametrize("value", [0, -1, None])
def test_no_quota_means_no_limit(value):
    """★0 은 「제한 없음」이다. 「즉시 거부」가 아니다 — 뒤집히면 전부 막힌다."""
    assert interval_for(value) == 0.0
    limiter = RateLimiter(intervals={"src": interval_for(value)})
    for _ in range(5):
        limiter.acquire("src")      # 예외가 나면 실패


# ── 통과·대기·거부 ──────────────────────────────────────────────
def test_the_first_call_is_never_delayed():
    limiter, clock = _limiter(1_000)
    limiter.acquire("src")
    assert clock.slept == []


def test_a_call_after_the_interval_is_not_delayed():
    limiter, clock = _limiter(10_000)          # 8.64초
    limiter.acquire("src")
    clock.advance(9.0)
    limiter.acquire("src")
    assert clock.slept == []


def test_a_slightly_early_call_waits_instead_of_failing():
    """★조금 이르면 기다린다 — 거부보다 대기가 낫다."""
    limiter, clock = _limiter(10_000, max_wait=5.0)   # 8.64초
    limiter.acquire("src")
    clock.advance(6.0)
    limiter.acquire("src")
    assert clock.slept == [pytest.approx(2.64)]


def test_a_far_too_early_call_is_refused_not_slept_through():
    """★★86초를 자면 고객 요청이 그만큼 멈춘다. 실패보다 나쁘다."""
    limiter, clock = _limiter(1_000, max_wait=5.0)    # 86.4초
    limiter.acquire("src")
    with pytest.raises(RateLimited) as caught:
        limiter.acquire("src")
    assert clock.slept == [], "거부해야 하는데 잤다"
    assert caught.value.wait_seconds == pytest.approx(86.4)
    assert limiter.refusals["src"] == 1


def test_refusals_are_counted():
    """★세지 않으면 한도에 눌리고 있다는 걸 아무도 모른다."""
    limiter, _ = _limiter(1_000)
    limiter.acquire("src")
    for _ in range(3):
        with pytest.raises(RateLimited):
            limiter.acquire("src")
    assert limiter.refusals["src"] == 3


def test_the_stamp_is_taken_after_waiting_not_before():
    """★기다리기 전 시각으로 찍으면 간격이 조금씩 짧아져 결국 한도를 넘는다."""
    limiter, clock = _limiter(10_000, max_wait=100.0)   # 8.64초
    limiter.acquire("src")
    clock.advance(1.0)
    limiter.acquire("src")            # 7.64초 잔다 -> now = 8.64
    clock.advance(1.0)                # now = 9.64
    limiter.acquire("src")            # 다시 7.64초 자야 맞다
    assert clock.slept == [pytest.approx(7.64), pytest.approx(7.64)]


def test_sources_are_counted_separately():
    clock = _Clock()
    limiter = RateLimiter(
        intervals={"a": interval_for(1_000), "b": interval_for(1_000)},
        max_wait_seconds=0.0, clock=clock, sleep=clock.sleep)
    limiter.acquire("a")
    limiter.acquire("b")              # ★다른 소스라 막히면 안 된다
    with pytest.raises(RateLimited):
        limiter.acquire("a")


def test_an_unknown_source_is_not_limited():
    """★이름이 어긋나면 제한이 조용히 안 걸린다 — 그 사실을 시험이 말한다."""
    limiter, _ = _limiter(1_000)
    for _ in range(5):
        limiter.acquire("이름이 다른 소스")


# ── 어댑터가 실제로 이걸 지키는가 ────────────────────────────────
class _Probe(TravelSource):
    name = "src"


def _probe(limiter) -> _Probe:
    def transport(url, params):
        return httpx.Response(200, json={"ok": True},
                              request=httpx.Request("GET", url))
    return _Probe(transport=transport, limiter=limiter)


def test_an_adapter_without_a_limiter_is_unrestricted():
    """★단위 시험은 제한 없이 돈다. 조립만 제한기를 넣는다."""
    probe = _probe(None)
    for _ in range(5):
        assert probe._fetch_json("https://x", {}) == {"ok": True}


def test_a_refused_call_becomes_unknown_and_never_goes_out():
    """★거부는 예외로 위에 안 던진다 — 「모름」은 정상 갈래다."""
    limiter, _ = _limiter(1_000, max_wait=0.0)
    probe = _probe(limiter)
    calls = []
    probe._get = lambda url, params: (
        calls.append(url) or httpx.Response(200, json={"ok": True},
                                            request=httpx.Request("GET", url)))

    assert probe._fetch_json("https://x", {}) == {"ok": True}
    assert probe._fetch_json("https://x", {}) is None      # 거부
    assert len(calls) == 1, "거부됐는데 바깥으로 나갔다"
    assert probe.misses["rate_limited"] == 1


def test_the_xml_path_is_gated_too():
    """★JSON 만 막고 XML 을 안 막으면 국가유산청이 제한을 비켜 간다."""
    limiter, _ = _limiter(1_000, max_wait=0.0)
    probe = _probe(limiter)
    probe._get = lambda url, params: httpx.Response(
        200, text="<result/>", request=httpx.Request("GET", url))

    assert probe._fetch_xml("https://x", {}) == "<result/>"
    assert probe._fetch_xml("https://x", {}) is None
    assert probe.misses["rate_limited"] == 1


# ── 설정과 어댑터 이름이 맞는가 ─────────────────────────────────
def test_every_configured_source_name_matches_a_real_adapter():
    """★★이름이 하나라도 어긋나면 그 소스만 **조용히 제한 없이** 나간다.

    설정에서 오타를 내면 아무 오류도 안 나고 제한만 사라진다 — 가장 위험한
    종류의 실수라 여기서 센다.
    """
    from app.core.settings import Settings
    from app.infrastructure.travel.heritage import HeritageSource
    from app.infrastructure.travel.holiday import HolidaySource
    from app.infrastructure.travel.open_meteo import OpenMeteoWeather
    from app.infrastructure.travel.tour_api import TourApiPlace

    configured = set(Settings.model_construct().source_rate_limits())
    implemented = {OpenMeteoWeather.name, HeritageSource.name,
                   HolidaySource.name, TourApiPlace.name}

    missing = sorted(implemented - configured)
    assert not missing, (
        f"어댑터는 있는데 속도 설정에 이름이 없다: {missing}\n"
        f"  → 그 소스는 제한 없이 나간다. `Settings.source_rate_limits()` 에 넣는다.")
