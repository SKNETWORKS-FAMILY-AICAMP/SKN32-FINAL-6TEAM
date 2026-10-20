# -*- coding: utf-8 -*-
"""숙소 모드 · 언리미티드 모드 — 관리 콘솔 값이 먼저, 없으면 가드레일(둘 다 기본 끔). `[2026-10-19 사용자 결정]`

지키려는 것
 ①관리 콘솔 목록에 두 칸이 있다 — 숙소 모드는 「숙소 시연 모드 · 테스트 모드 · 끄기」(기본 끄기), 언리미티드는 참/거짓(기본 꺼짐)
 ②콘솔 값이 먼저 · 목록 밖 · 참/거짓 아닌 값 · 표를 못 읽음은 기본(끔)으로 간다 — 켜는 것은 명시한 경우뿐
 ③바깥 호출 문(ports)은 조립이 꽂기 전에는 한도 그대로 · 숙소 모드 off 다
 ④언리미티드면 호출 간격(`RateLimiter`)으로 거절하지 않는다
 ⑤구글 호텔 호출 문(`LodgingModeLimiter`)은 off 면 바깥에 안 나가고, test · demo 면 그 제한기를 쓴다 — 구글 항공권은 이 문을 안 쓴다

DB 를 쓰는 횟수 시험(모드별로 SerpApi 를 몇 번까지 부르나)은 `tests/integration/db/test_lodging_unlimited_budget_db.py`.
"""
from __future__ import annotations

import httpx
import pytest

from app.core.settings import Settings
from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.ports.data_sources import operator_modes
from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
from app.domains.travel_ops.ports.data_sources.ratelimit import RateLimited, RateLimiter
from app.domains.travel_ops.ports.data_sources.serpapi_hotels import SerpApiHotels
from app.domains.travel_ops.ports.data_sources.source_budget import BudgetedLimiter, LodgingModeLimiter, LodgingModeOff


@pytest.fixture(autouse=True)
def _clean_hooks():
    settings_hook.clear()
    operator_modes.clear()
    yield
    settings_hook.clear()
    operator_modes.clear()


# ── ① 관리 콘솔 목록 ─────────────────────────────────────────────
def test_lodging_mode_is_listed_with_the_three_labels_and_off_by_default():
    assert web_guard.LODGING_MODE_NAME == settings_hook.LODGING_MODE
    spec = web_guard.specs()[settings_hook.LODGING_MODE]
    assert (spec.type, spec.default, spec.choices) == ("choice", "off", ("demo", "test", "off"))
    assert dict(spec.choice_labels) == {"demo": "숙소 시연 모드", "test": "테스트 모드", "off": "끄기"}
    assert spec.check("demo") is None and spec.check("on") == "not_a_choice" and spec.check(True) == "wrong_type"
    assert "SerpApi" in spec.help and "월" in spec.help


def test_unlimited_mode_is_listed_off_by_default_with_a_paid_call_warning():
    assert web_guard.UNLIMITED_MODE_NAME == settings_hook.UNLIMITED_MODE
    spec = web_guard.specs()[settings_hook.UNLIMITED_MODE]
    assert (spec.type, spec.default) == ("bool", False)
    assert spec.check(True) is None and spec.check("on") == "wrong_type"
    assert "유료 호출이 늘 수 있" in spec.help


# ── ② 콘솔 값이 먼저 ─────────────────────────────────────────────
def test_without_console_values_both_modes_are_off():
    assert settings_hook.lodging_mode("t1") == "off"
    assert settings_hook.unlimited_mode("t1") is False


@pytest.mark.parametrize("stored", ["demo", "test", "off"])
def test_console_lodging_mode_wins(stored):
    settings_hook.register(lambda tenant, name: stored if name == settings_hook.LODGING_MODE else None)
    assert settings_hook.lodging_mode("t1") == stored


@pytest.mark.parametrize("stored", ["on", True, 1, None, "DEMO"])
def test_lodging_mode_outside_the_list_is_off(stored):
    settings_hook.register(lambda tenant, name: stored)
    assert settings_hook.lodging_mode("t1") == "off"


@pytest.mark.parametrize("stored, expected", [(True, True), (False, False), ("on", False), (1, False), (None, False)])
def test_only_a_real_true_turns_unlimited_on(stored, expected):
    settings_hook.register(lambda tenant, name: stored if name == settings_hook.UNLIMITED_MODE else None)
    assert settings_hook.unlimited_mode("t1") is expected


def test_unreadable_settings_keep_both_modes_off():
    def broken(tenant, name):
        raise RuntimeError("db down")

    settings_hook.register(broken)
    assert settings_hook.lodging_mode("t1") == "off"
    assert settings_hook.unlimited_mode("t1") is False


# ── ③ 바깥 호출 문의 끼움 자리 ────────────────────────────────────
def test_ports_default_to_limits_kept_and_lodging_off_until_wired():
    assert operator_modes.unlimited() is False
    assert operator_modes.lodging_mode() == "off"
    operator_modes.register(unlimited=lambda: True, lodging_mode=lambda: "demo")
    assert operator_modes.unlimited() is True and operator_modes.lodging_mode() == "demo"


def test_ports_treat_a_broken_reader_as_off():
    def broken():
        raise RuntimeError("boom")

    operator_modes.register(unlimited=broken, lodging_mode=broken)
    assert operator_modes.unlimited() is False
    assert operator_modes.lodging_mode() == "off"
    operator_modes.register(lodging_mode=lambda: "everything")
    assert operator_modes.lodging_mode() == "off"


# ── ④ 언리미티드면 호출 간격으로 거절하지 않는다 ─────────────────────
def _limiter() -> RateLimiter:
    clock = iter(range(1000, 2000))
    return RateLimiter(intervals={"kma": 3600.0}, max_wait_seconds=0.0, clock=lambda: float(next(clock)), sleep=lambda s: None)


def test_rate_limiter_refuses_the_second_call_when_limits_are_kept():
    limiter = _limiter()
    limiter.acquire("kma")
    with pytest.raises(RateLimited):
        limiter.acquire("kma")


def test_rate_limiter_lets_every_call_through_in_unlimited_mode():
    operator_modes.register(unlimited=lambda: True)
    limiter = _limiter()
    for _ in range(20):
        limiter.acquire("kma")
    assert limiter.refusals == {}


# ── ⑤ 구글 호텔 호출 문 ──────────────────────────────────────────
class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def acquire(self, source: str) -> None:
        self.calls.append(source)


@pytest.mark.parametrize("mode, used", [("test", "test"), ("demo", "demo")])
def test_the_hotel_gate_uses_the_limiter_of_the_current_mode(mode, used):
    test, demo = _Recorder(), _Recorder()
    operator_modes.register(lodging_mode=lambda: mode)
    LodgingModeLimiter(test=test, demo=demo).acquire("serpapi")
    assert {"test": test, "demo": demo}[used].calls == ["serpapi"]
    assert {"test": demo, "demo": test}[used].calls == []


def test_the_hotel_gate_does_not_go_out_when_lodging_mode_is_off():
    test, demo = _Recorder(), _Recorder()
    with pytest.raises(LodgingModeOff) as raised:
        LodgingModeLimiter(test=test, demo=demo).acquire("serpapi")
    assert raised.value.reason == "lodging_mode_off" and isinstance(raised.value, RateLimited)
    assert test.calls == demo.calls == []


def _hotels(gate) -> tuple[SerpApiHotels, list[dict]]:
    sent: list[dict] = []

    def transport(url, params):
        sent.append(params)
        return httpx.Response(200, json={"properties": []}, request=httpx.Request("GET", url))

    return SerpApiHotels(api_key="test", transport=transport, limiter=gate), sent


def test_off_mode_makes_no_serpapi_request_and_records_a_quiet_miss():
    hotels, sent = _hotels(LodgingModeLimiter(test=_Recorder(), demo=_Recorder()))
    assert hotels.stay_search(keyword="명동", check_in="2026-11-06", check_out="2026-11-07", adults=2) is None
    assert sent == []
    assert hotels.misses["lodging_mode_off"] == 1


@pytest.mark.parametrize("mode", ["test", "demo"])
def test_test_and_demo_modes_send_the_request(mode):
    operator_modes.register(lodging_mode=lambda: mode)
    hotels, sent = _hotels(LodgingModeLimiter(test=_Recorder(), demo=_Recorder()))
    hotels.stay_search(keyword="명동", check_in="2026-11-06", check_out="2026-11-07", adults=2)
    assert len(sent) == 1


def test_assembly_puts_only_google_hotels_behind_the_lodging_gate():
    """조립(`build_travel_sources`) — 구글 호텔만 숙소 모드 문 뒤에, 구글 항공권은 보통 제한기. 시연 제한기는 `serpapi` 의 간격 · 하루 줄 · 몫을 뺀다."""
    settings = Settings.model_construct(serpapi_api_key="test")
    sources = build_travel_sources(settings, low_priority_share=0.25)
    gate = sources.stay_google._limiter
    assert isinstance(gate, LodgingModeLimiter)
    assert sources.flight_google._limiter is sources.limiter
    test, demo = gate._test, gate._demo
    assert test is sources.limiter
    assert isinstance(test, BudgetedLimiter) and isinstance(demo, BudgetedLimiter)
    assert test._budget.share == 0.25 and test._budget.soft_day == frozenset()
    assert demo._budget.share == 1.0 and demo._budget.soft_day == frozenset({"serpapi"})
    assert test._budget.caps["serpapi"] == demo._budget.caps["serpapi"] == {"day": 8, "month": 250}
    assert "serpapi" in test._inner.intervals and "serpapi" not in demo._inner.intervals
    assert demo._on_db_error == "refuse", "시연은 월 한도가 유일한 둑이라 DB 를 못 읽으면 부르지 않는다"


def test_cache_only_assembly_keeps_hotels_from_going_out():
    from app.domains.travel_ops.ports.data_sources.ratelimit import CacheOnlyLimiter

    sources = build_travel_sources(Settings.model_construct(serpapi_api_key="test"), cache_only=True)
    assert isinstance(sources.stay_google._limiter, CacheOnlyLimiter)
