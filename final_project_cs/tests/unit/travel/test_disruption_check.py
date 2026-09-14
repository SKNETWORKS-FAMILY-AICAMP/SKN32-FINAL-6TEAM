# -*- coding: utf-8 -*-
"""일정 성립 점검 — 판정 규칙(치명·이상·통과)과 「해당 없음/미연결/실패」를 가른다.

★사용자 결정(2026-09-14):
    이상이 **하나라도** 있으면 일정 변경 대상(disrupted)
    항목이 **하나라도** 1차·대체까지 실패하면 치명(fatal) — 조회 실패로 일정을 바꾸지 않는다
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import NOT_CONNECTED, DisruptionCheck
from app.infrastructure.travel.weather_chain import FallbackWeather
from app.tools.read_tools import ReadToolbox, ToolContext

OUTDOOR = {"place_id": "p1", "latitude": 37.58, "longitude": 126.98, "weather_sensitive": True}
INDOOR = {**OUTDOOR, "weather_sensitive": False}
AT = datetime(2026, 9, 15, 14)
LIMITS = lambda: (60, 30)   # noqa: E731 — 주의 기준(가드레일 값과 무관하게 고정)


class _Weather:
    def __init__(self, value, name="open_meteo"):
        self.value, self.name, self.calls = value, name, 0

    def forecast(self, **_):
        self.calls += 1
        return self.value


class _Warning:
    name = "kma_warning"

    def __init__(self, value):
        self.value, self.calls = value, 0

    def active(self, *, region):
        self.calls += 1
        return self.value


def _fc(pop=10, wind=5.0, source="open_meteo"):
    return {"precipitation_probability": pop, "wind_speed_kmh": wind, "source": source,
            "confirmed_at": "x", "matched_hour": "2026-09-15T14:00"}


def _warn(*kinds):
    return {"for_region": [{"kind": k, "areas": ["서울동남권"]} for k in kinds],
            "source": "kma_warning", "announced_at": "2026-09-15T08:00", "confirmed_at": "x"}


def _check(weather, warning, place=OUTDOOR):
    sources = TravelSources(weather=weather, warning=warning)
    return DisruptionCheck(sources, limits=LIMITS).check(place=place, starts_at=AT)


# ── 판정 규칙 ────────────────────────────────────────────────────
def test_all_quiet_is_clear():
    report = _check(_Weather(_fc()), _Warning(_warn()))
    assert report["verdict"] == "clear"
    assert report["disruptions"] == [] and report["failed_categories"] == []


def test_one_warning_is_enough_to_disrupt():
    report = _check(_Weather(_fc()), _Warning(_warn("호우경보")))
    assert report["verdict"] == "disrupted"
    assert [d["kind"] for d in report["disruptions"]] == ["호우경보"]


def test_one_failed_category_is_fatal_even_if_another_found_a_disruption():
    """★치명이 이상보다 앞선다 — 못 본 항목이 있으면 판정 자체를 못 믿는다."""
    report = _check(_Weather(None), _Warning(_warn("호우경보")))
    assert report["verdict"] == "fatal"
    assert report["failed_categories"] == ["forecast"]


def test_a_failed_warning_lookup_is_fatal_not_no_warning():
    report = _check(_Weather(_fc()), _Warning(None))
    assert report["verdict"] == "fatal"
    assert report["failed_categories"] == ["weather_warning"]


def test_high_forecast_numbers_are_advisories_not_disruptions():
    """★수치로 일정을 바꾸지 않는다 — 운영 규정이 정할 일이다."""
    report = _check(_Weather(_fc(pop=90, wind=40)), _Warning(_warn()))
    assert report["verdict"] == "clear"
    assert {a["field"] for a in report["advisories"]} == {"precipitation_probability",
                                                          "wind_speed_kmh"}


# ── 해당 없음 · 미연결 · 실패 ────────────────────────────────────
def test_an_indoor_place_does_not_call_weather_sources_at_all():
    weather, warning = _Weather(None), _Warning(None)
    report = _check(weather, warning, place=INDOOR)
    assert report["verdict"] == "clear"
    assert weather.calls == 0 and warning.calls == 0
    statuses = {c["category"]: c["status"] for c in report["checks"]}
    assert statuses["forecast"] == statuses["weather_warning"] == "not_applicable"


def test_unconnected_sources_are_listed_not_hidden_and_not_fatal():
    report = _check(_Weather(_fc()), _Warning(_warn()))
    # ★재난문자는 소스가 없으면 미연결로 잡힌다(샘플 판이 없는 이 시험 조립)
    assert set(report["not_connected"]) == set(NOT_CONNECTED) | {"disaster_msg", "traffic_control"}
    assert report["verdict"] == "clear"


def test_missing_coordinates_fail_the_forecast_instead_of_guessing_a_place():
    report = _check(_Weather(_fc()), _Warning(_warn()),
                    place={**OUTDOOR, "latitude": None})
    assert report["verdict"] == "fatal"
    forecast = next(c for c in report["checks"] if c["category"] == "forecast")
    assert forecast["reason"] == "장소 좌표 없음"


def test_a_missing_warning_source_is_unconnected_with_its_reason():
    sources = TravelSources(weather=_Weather(_fc()), unavailable={"warning": "키 없음"})
    report = DisruptionCheck(sources, limits=LIMITS).check(place=OUTDOOR, starts_at=AT)
    warning = next(c for c in report["checks"] if c["category"] == "weather_warning")
    assert warning == {"category": "weather_warning", "status": "not_connected", "reason": "키 없음"}


def test_the_forecast_chain_fallback_is_visible_and_all_tried_sources_are_named():
    chain = FallbackWeather([_Weather(None, "open_meteo"), _Weather(_fc(source="kma"), "kma")])
    report = _check(chain, _Warning(_warn()))
    forecast = next(c for c in report["checks"] if c["category"] == "forecast")
    assert forecast["source"] == "kma" and forecast["fell_back_from"] == ["open_meteo"]

    dead = FallbackWeather([_Weather(None, "open_meteo"), _Weather(None, "kma")])
    failed = next(c for c in _check(dead, _Warning(_warn()))["checks"]
                  if c["category"] == "forecast")
    assert failed["status"] == "failed" and failed["tried"] == ["open_meteo", "kma"]


# ── 도구 배선 ────────────────────────────────────────────────────
SCOPE = ToolContext(tenant_id="t", customer_id=uuid4(), case_id=uuid4(),
                    knowledge_scope=["activity"])


def test_the_tool_does_not_go_out_without_injected_sources():
    assert ReadToolbox(lambda: None).disruptions(SCOPE, latitude=37.5, longitude=127.0,
                                                 weather_sensitive=True) is None


def test_the_tool_runs_the_check_over_injected_sources():
    toolbox = ReadToolbox(lambda: None, travel=TravelSources(
        weather=_Weather(_fc()), warning=_Warning(_warn("태풍경보"))))
    report = toolbox.disruptions(SCOPE, place_id="p1", latitude=37.5, longitude=127.0,
                                 weather_sensitive=True, starts_at="2026-09-15T14:00:00+09:00")
    assert report["verdict"] == "disrupted" and report["place_id"] == "p1"
    assert report["starts_at"].startswith("2026-09-15T14:00")
