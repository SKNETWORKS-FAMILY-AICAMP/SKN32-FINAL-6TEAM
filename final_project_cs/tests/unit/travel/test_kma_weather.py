# -*- coding: utf-8 -*-
"""기상청 단기예보 어댑터와 대체 소스 사슬.

★실제 공급자 응답 모양(2026-09-14 실호출)을 그대로 흉내 낸다. 네트워크는 안 탄다.
"""
from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from app.infrastructure.travel.kma import (
    KST, KmaWeather, latest_issue, parse_precipitation, to_grid)
from app.infrastructure.travel.weather_chain import FallbackWeather

NOW = datetime(2026, 9, 14, 9, 30, tzinfo=KST)


def _resp(status: int, payload=None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://x")
    if text is not None:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=payload, request=request)


def _ok(items):
    return {"response": {"header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
                         "body": {"items": {"item": items}}}}


def _items(date="20260914", time="1200", **values):
    base = {"TMP": "21", "POP": "30", "PCP": "강수없음", "WSD": "2.5"}
    base.update(values)
    return [{"category": k, "fcstDate": date, "fcstTime": time, "fcstValue": v}
            for k, v in base.items()]


def _source(handler) -> KmaWeather:
    return KmaWeather(service_key="k", now=lambda: NOW,
                      transport=lambda url, params: handler(url, params))


# ── 격자 · 발표 시각 · 강수량 표기 ─────────────────────────────
def test_seoul_city_hall_maps_to_the_kma_grid_table():
    """★기상청 격자표: 서울 중구(서울시청) = (60, 127)."""
    assert to_grid(37.5665, 126.9780) == (60, 127)


@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 9, 14, 9, 30, tzinfo=KST), datetime(2026, 9, 14, 8, tzinfo=KST)),
    (datetime(2026, 9, 14, 8, 5, tzinfo=KST), datetime(2026, 9, 14, 5, tzinfo=KST)),   # 발표 후 10분 전
    (datetime(2026, 9, 14, 1, 0, tzinfo=KST), datetime(2026, 9, 13, 23, tzinfo=KST)),  # 02시 전 → 전날
])
def test_latest_issue_respects_the_ten_minute_delay(now, expected):
    assert latest_issue(now) == expected


@pytest.mark.parametrize("text,mm", [
    ("강수없음", 0.0), ("1mm 미만", 0.1), ("1.0mm", 1.0),
    ("30.0~50.0mm", 30.0), ("50.0mm 이상", 50.0), ("뭔가이상", None), (None, None),
])
def test_precipitation_text_is_parsed_without_inventing_an_upper_bound(text, mm):
    assert parse_precipitation(text) == mm


# ── 성공: Open-Meteo 와 같은 모양, 단위 환산 ────────────────────
def test_success_has_the_same_shape_as_open_meteo_and_converts_wind_units():
    seen = {}

    def handler(url, params):
        seen.update(params)
        return _resp(200, _ok(_items(WSD="2.5")))

    result = _source(handler).forecast(
        latitude=37.5665, longitude=126.9780, at=datetime(2026, 9, 14, 12, 40, tzinfo=KST))
    assert (seen["nx"], seen["ny"], seen["base_time"]) == (60, 127, "0800")
    assert result["matched_hour"] == "2026-09-14T12:00"
    assert result["temperature_c"] == 21.0
    assert result["precipitation_probability"] == 30
    assert result["precipitation_mm"] == 0.0
    # ★m/s → km/h. 환산을 빼먹으면 풍속이 3.6배 작게 보여 주의 문구가 안 뜬다
    assert result["wind_speed_kmh"] == 9.0
    assert result["kind"] == "forecast" and result["source"] == "kma"
    assert result["confirmed_at"]


def test_naive_time_is_read_as_kst():
    result = _source(lambda u, p: _resp(200, _ok(_items(time="1500")))).forecast(
        latitude=37.5665, longitude=126.9780, at=datetime(2026, 9, 14, 15, 0))
    assert result is not None and result["matched_hour"] == "2026-09-14T15:00"


# ── 실패는 전부 「모름」이고 전부 세어진다 ──────────────────────
@pytest.mark.parametrize("payload,reason", [
    ({"response": {"header": {"resultCode": "03", "resultMsg": "NO_DATA"}}}, "body_error"),
    ({"response": {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}},
     "body_error"),
    ({"response": {"header": {"resultCode": "00"}, "body": {"items": ""}}}, "empty_items"),
])
def test_http_200_with_a_non_00_code_is_a_miss(payload, reason):
    """★기상청은 `NO_DATA` 도 HTTP 200 이다. 빈 표를 「확인했다」로 읽으면 안 된다."""
    source = _source(lambda u, p: _resp(200, payload))
    assert source.forecast(latitude=37.5, longitude=127.0,
                           at=datetime(2026, 9, 14, 12, tzinfo=KST)) is None
    assert source.misses[reason] == 1, dict(source.misses)


def test_an_hour_outside_the_table_is_unknown_not_the_nearest_hour():
    source = _source(lambda u, p: _resp(200, _ok(_items(time="1200"))))
    assert source.forecast(latitude=37.5, longitude=127.0,
                           at=datetime(2026, 9, 20, 12, tzinfo=KST)) is None
    assert source.misses["hour_not_in_response"] == 1


def test_a_time_before_the_forecast_window_does_not_call_out():
    calls = []
    source = _source(lambda u, p: calls.append(1) or _resp(200, _ok(_items())))
    assert source.forecast(latitude=37.5, longitude=127.0,
                           at=datetime(2026, 9, 13, 12, tzinfo=KST)) is None
    assert calls == [] and source.misses["before_forecast_window"] == 1


# ── 대체 소스 사슬 (결정 15) ────────────────────────────────────
class _Fixed:
    def __init__(self, name, value):
        self.name, self.value, self.calls = name, value, 0

    def forecast(self, **_):
        self.calls += 1
        return self.value


def test_the_primary_answers_and_the_fallback_is_not_called():
    primary, backup = _Fixed("open_meteo", {"source": "open_meteo"}), _Fixed("kma", {"source": "kma"})
    result = FallbackWeather([primary, backup]).forecast(latitude=1, longitude=2)
    assert result == {"source": "open_meteo"} and backup.calls == 0


def test_when_the_primary_fails_the_fallback_answers_and_says_so():
    chain = FallbackWeather([_Fixed("open_meteo", None), _Fixed("kma", {"source": "kma"})])
    result = chain.forecast(latitude=1, longitude=2)
    assert result["source"] == "kma"
    # ★대체로 넘어간 사실을 숨기지 않는다
    assert result["fell_back_from"] == ["open_meteo"]
    assert chain.misses["fell_back"] == 1


def test_when_every_source_fails_it_is_counted_as_all_failed():
    chain = FallbackWeather([_Fixed("open_meteo", None), _Fixed("kma", None)])
    assert chain.forecast(latitude=1, longitude=2) is None
    assert chain.misses["all_failed"] == 1
