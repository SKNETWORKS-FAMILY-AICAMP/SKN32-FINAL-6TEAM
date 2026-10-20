# -*- coding: utf-8 -*-
"""숙소 모드 · 언리미티드 모드별로 구글 호텔(SerpApi)을 **몇 번까지** 부르나 — 실제 DB 예산 + mock HTTP. `[2026-10-19 사용자 결정]`

★실제 SerpApi 는 부르지 않는다 — 어댑터의 HTTP 자리(`transport`)에 응답 흉내를 꽂고 나간 요청 수를 센다.
★예산 줄 이름은 시험마다 새로 만든다(`t_<무작위>`) — 개발 DB 의 진짜 `serpapi` 줄을 건드리지 않고, 끝나면 그 줄과 `:uncapped` 줄만 지운다.
  조립(`build_travel_sources`)과 같은 모양으로 문을 만든다: 보통 제한기(test) · 시연 제한기(demo — 하루 줄을 풀고 월 줄만) · 숙소 모드 문.

지키려는 것(하루 3 · 월 5 로 줄여서)
 off            0번 — 바깥에 안 나간다
 test           하루 3번에서 멈춘다 · 확인 화면 몫(1/3)이면 1번
 demo           하루 줄을 넘어 월 5번까지 — 하루 상한을 넘긴 2번은 `:uncapped` 하루 줄에 센다
 demo + 언리미티드 · test + 언리미티드   월 줄도 넘어 10번 모두 — 넘긴 것은 `:uncapped` 줄에 센다
 언리미티드를 끄면 다시 한도에서 멈춘다
그리고 관리 콘솔 「API 호출량」 표(`api_limits.snapshot`)가 `:uncapped` 줄을 「한도 밖」 수로 보인다.

재현:

    python -m pytest tests/integration/db/test_lodging_unlimited_budget_db.py -v
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.ports.data_sources import operator_modes
from app.domains.travel_ops.ports.data_sources.ratelimit import RateLimiter
from app.domains.travel_ops.ports.data_sources.serpapi_hotels import SerpApiHotels
from app.domains.travel_ops.ports.data_sources.source_budget import LodgingModeLimiter, with_db_budget

KST = ZoneInfo("Asia/Seoul")
DAY, MONTH, TRIES = 3, 5, 10


@pytest.fixture()
def meter():
    name = "t_" + uuid4().hex[:10]
    operator_modes.clear()
    yield name
    operator_modes.clear()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM external_call_budget WHERE meter IN (%s, %s)", (name, f"{name}:uncapped"))


def _gate(meter: str, *, share: float = 1.0) -> LodgingModeLimiter:
    """조립과 같은 모양 — 보통(test) · 시연(demo, 하루 줄 풂 · 몫 없음) 제한기를 숙소 모드 문이 고른다."""
    test = with_db_budget(RateLimiter(), {meter: DAY}, {meter: MONTH}, [meter], share=share)
    demo = with_db_budget(RateLimiter(), {meter: DAY}, {meter: MONTH}, [meter], soft_day=frozenset({meter}))
    return LodgingModeLimiter(test=test, demo=demo)


def _hotels(meter: str, gate: LodgingModeLimiter) -> tuple[SerpApiHotels, list[dict]]:
    sent: list[dict] = []

    def transport(url, params):
        sent.append(params)
        return httpx.Response(200, json={"properties": [{"name": f"호텔 {len(sent)}", "gps_coordinates": {"latitude": 37.56, "longitude": 126.98}}]},
                              request=httpx.Request("GET", url))

    hotels = SerpApiHotels(api_key="test", transport=transport, limiter=gate)
    hotels.name = meter                     # 줄 이름만 시험용으로 — 문 · 예산은 조립과 같다
    return hotels, sent


def _search(hotels: SerpApiHotels, times: int = TRIES) -> None:
    for _ in range(times):
        hotels.stay_search(keyword="명동", check_in="2026-11-06", check_out="2026-11-07", adults=2)


def _rows(meter: str) -> dict[str, int]:
    """{"day" · "month" · "day:uncapped" · "month:uncapped": used}"""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT meter, period, used FROM external_call_budget WHERE meter IN (%s, %s)", (meter, f"{meter}:uncapped"))
        found = cur.fetchall()
    return {period.split(":", 1)[0] + (":uncapped" if name.endswith(":uncapped") else ""): int(used) for name, period, used in found}


def test_off_never_calls_serpapi(meter):
    hotels, sent = _hotels(meter, _gate(meter))
    _search(hotels)
    assert sent == []
    assert _rows(meter) == {}, "부르지 않았으니 예산 줄도 안 생긴다"
    assert hotels.misses["lodging_mode_off"] == TRIES


def test_test_mode_stops_at_the_daily_cap(meter):
    operator_modes.register(lodging_mode=lambda: "test")
    hotels, sent = _hotels(meter, _gate(meter))
    _search(hotels)
    assert len(sent) == DAY
    assert _rows(meter) == {"day": DAY, "month": DAY}
    assert hotels.misses["budget_exhausted"] == TRIES - DAY


def test_test_mode_on_the_confirm_screen_uses_only_its_share(meter):
    operator_modes.register(lodging_mode=lambda: "test")
    hotels, sent = _hotels(meter, _gate(meter, share=0.34))       # 하루 3 × 0.34 → 1
    _search(hotels)
    assert len(sent) == 1


def test_demo_mode_has_no_daily_cap_but_keeps_the_monthly_cap(meter):
    operator_modes.register(lodging_mode=lambda: "demo")
    hotels, sent = _hotels(meter, _gate(meter, share=0.34))       # ★시연은 몫도 무시한다
    _search(hotels)
    assert len(sent) == MONTH
    assert _rows(meter) == {"day": DAY, "month": MONTH, "day:uncapped": MONTH - DAY}
    assert hotels.misses["budget_exhausted"] == TRIES - MONTH


@pytest.mark.parametrize("mode", ["demo", "test"])
def test_unlimited_mode_lifts_the_monthly_cap_too_and_still_counts(meter, mode):
    operator_modes.register(lodging_mode=lambda: mode, unlimited=lambda: True)
    hotels, sent = _hotels(meter, _gate(meter, share=0.34))
    _search(hotels)
    assert len(sent) == TRIES
    rows = _rows(meter)
    assert (rows["day"], rows["month"]) == (DAY, MONTH), "상한 있는 줄은 상한까지"
    assert rows["month:uncapped"] == TRIES - MONTH and rows["day:uncapped"] == TRIES - DAY, "넘긴 호출은 따로 센다"


def test_unlimited_does_not_turn_on_serpapi_when_lodging_mode_is_off(meter):
    operator_modes.register(lodging_mode=lambda: "off", unlimited=lambda: True)
    hotels, sent = _hotels(meter, _gate(meter))
    _search(hotels)
    assert sent == []


def test_turning_unlimited_off_brings_the_caps_back(meter):
    state = {"unlimited": True}
    operator_modes.register(lodging_mode=lambda: "test", unlimited=lambda: state["unlimited"])
    hotels, sent = _hotels(meter, _gate(meter))
    _search(hotels, 4)
    assert len(sent) == 4
    state["unlimited"] = False
    _search(hotels, 3)
    assert len(sent) == 4, "하루 줄이 이미 찼다 — 끄자마자 다시 멈춘다"


def test_provider_quota_block_stays_even_in_unlimited_mode(meter):
    """제공처가 「한도 초과」라고 알린 줄은 언리미티드에서도 멈춘다(제공처가 어차피 거절한다)."""
    operator_modes.register(lodging_mode=lambda: "test", unlimited=lambda: True)
    gate = _gate(meter)
    hotels, sent = _hotels(meter, gate)
    _search(hotels, 1)
    gate.mark_provider_exhausted(meter, "month")
    _search(hotels, 3)
    assert len(sent) == 1


def test_the_admin_usage_table_shows_calls_over_the_cap(monkeypatch):
    """관리 콘솔 「API 호출량」 — `serpapi:uncapped` 줄을 그 API 의 「한도 밖」 수로 보인다(상한 있는 줄과 따로)."""
    from app.application.api_limits import snapshot

    now = datetime(2026, 10, 19, 21, 0, tzinfo=KST)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM external_call_budget WHERE meter = 'serpapi:uncapped' AND period IN ('day:2026-10-19', 'month:2026-10')")
        cur.execute("INSERT INTO external_call_budget (meter, period, used, cap) VALUES ('serpapi:uncapped', 'day:2026-10-19', 4, 2000000000), "
                    "('serpapi:uncapped', 'month:2026-10', 6, 2000000000)")
    try:
        view = snapshot(connection_factory=get_connection, now=now)
        row = next(r for r in view["limits"] if r["id"] == "serpapi")
        assert row["name"] == "SerpApi 구글 호텔 · 항공권"
        assert row["over_cap"] == {"day": 4, "month": 6}
        assert next(r for r in view["limits"] if r["id"] == "kma")["over_cap"] is None
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM external_call_budget WHERE meter = 'serpapi:uncapped' AND period IN ('day:2026-10-19', 'month:2026-10')")
