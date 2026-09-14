# -*- coding: utf-8 -*-
"""바깥 소스 어댑터 — **못 가져왔을 때** 어떻게 구는지를 본다.

★잘 될 때보다 안 될 때가 중요하다. 이 저장소가 반복해서 데인 모양이
  「조용히 그럴듯한 값으로 메우기」이기 때문이다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from app.infrastructure.travel.base import TravelSource
from app.infrastructure.travel.open_meteo import MAX_FORECAST_DAYS, OpenMeteoWeather


def _response(status: int, payload=None, text: str | None = None) -> httpx.Response:
    if text is not None:
        return httpx.Response(status, text=text, request=httpx.Request("GET", "https://x"))
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://x"))


def _source(handler) -> OpenMeteoWeather:
    return OpenMeteoWeather(transport=lambda url, params: handler(url, params))


def _hourly(hour: str, **values):
    base = {"time": [hour], "temperature_2m": [20.0],
            "precipitation_probability": [10], "precipitation": [0.0],
            "wind_speed_10m": [5.0]}
    base.update({key: [value] for key, value in values.items()})
    return {"latitude": 37.5, "longitude": 127.0, "timezone": "Asia/Seoul", "hourly": base}


def _tomorrow_noon() -> datetime:
    return (datetime.now() + timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0)


# ── ★HTTP 200 인데 실패인 경우 ──────────────────────────────────
def test_http_200_with_an_error_body_is_a_miss_not_a_success():
    """★2026-09-09 실측 — ODsay 는 인증 실패에도 **HTTP 200** 을 준다.

        {"error":[{"code":"500","message":"[ApiKeyAuthFailed] ..."}]}

    `raise_for_status()` 만 믿으면 인증 실패가 성공으로 지나가고, Team 은
    빈 값을 「확인했다」로 읽는다.
    """
    source = _source(lambda url, params: _response(
        200, {"error": [{"code": "500", "message": "[ApiKeyAuthFailed] nope"}]}))
    assert source.forecast(latitude=37.5, longitude=127.0, at=_tomorrow_noon()) is None
    assert source.misses["body_error"] == 1


def test_data_go_kr_style_error_envelope_is_a_miss():
    """★공공데이터포털 계열은 `OpenAPI_ServiceResponse` 안에 오류를 넣는다."""
    source = _source(lambda url, params: _response(200, {
        "OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "SERVICE_KEY_IS_NULL"}}}))
    assert source.forecast(latitude=37.5, longitude=127.0, at=_tomorrow_noon()) is None
    assert source.misses["body_error"] == 1


# ── 실패 갈래는 전부 「모름」이고, 전부 세어진다 ─────────────────
@pytest.mark.parametrize("handler,reason", [
    (lambda url, params: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")), "timeout"),
    (lambda url, params: (_ for _ in ()).throw(httpx.ConnectError("down")), "transport_error"),
    (lambda url, params: _response(500, text="oops"), "http_500"),
    (lambda url, params: _response(200, text="<html>error</html>"), "not_json"),
    (lambda url, params: _response(200, {"hourly": {"time": []}}), "empty_hourly"),
])
def test_every_failure_is_none_and_is_counted(handler, reason):
    source = _source(handler)
    assert source.forecast(latitude=37.5, longitude=127.0, at=_tomorrow_noon()) is None
    assert source.misses[reason] == 1, dict(source.misses)


def test_a_timeout_is_not_retried():
    """★타임아웃에 자동 재시도를 걸면 공급자 장애 때 우리가 부하를 보탠다."""
    calls = []

    def handler(url, params):
        calls.append(url)
        raise httpx.ReadTimeout("slow")

    assert _source(handler).forecast(
        latitude=37.5, longitude=127.0, at=_tomorrow_noon()) is None
    assert len(calls) == 1, f"재시도했다: {len(calls)}회"


# ── 범위 밖은 늘려 잡지 않는다 ──────────────────────────────────
def test_a_date_beyond_the_forecast_window_is_unknown_not_extrapolated():
    called = []
    source = _source(lambda url, params: called.append(url) or _response(200, _hourly("x")))
    far = datetime.now() + timedelta(days=MAX_FORECAST_DAYS + 1)
    assert source.forecast(latitude=37.5, longitude=127.0, at=far) is None
    assert source.misses["outside_forecast_window"] == 1
    assert not called, "범위 밖인데 바깥으로 나갔다"


def test_a_past_date_is_unknown():
    source = _source(lambda url, params: _response(200, _hourly("x")))
    past = datetime.now() - timedelta(days=1)
    assert source.forecast(latitude=37.5, longitude=127.0, at=past) is None


def test_the_requested_hour_missing_from_the_table_is_unknown_not_nearest():
    """★가장 가까운 칸으로 바꿔치기하지 않는다 — 그게 폴백이다."""
    source = _source(lambda url, params: _response(200, _hourly("2026-01-01T03:00")))
    assert source.forecast(latitude=37.5, longitude=127.0, at=_tomorrow_noon()) is None
    assert source.misses["hour_not_in_response"] == 1


# ── 성공하면 확인 시각·출처가 반드시 붙는다 ─────────────────────
def test_a_success_carries_confirmed_at_source_and_the_matched_hour():
    target = _tomorrow_noon()
    key = target.strftime("%Y-%m-%dT%H:%M")
    source = _source(lambda url, params: _response(
        200, _hourly(key, precipitation_probability=70, wind_speed_10m=12.0)))

    result = source.forecast(latitude=37.5, longitude=127.0, at=target)
    assert result is not None
    assert result["source"] == "open_meteo"
    assert result["confirmed_at"]                 # 우리가 조회한 시각
    assert result["matched_hour"] == key          # 예보표에서 고른 칸
    assert result["kind"] == "forecast"           # ★관찰이 아니다
    assert result["precipitation_probability"] == 70


def test_a_missing_field_stays_none_and_is_not_zero_filled():
    """★없는 값을 0 으로 채우면 「바람이 없다」가 된다. 모르는 것과 다르다."""
    target = _tomorrow_noon()
    key = target.strftime("%Y-%m-%dT%H:%M")
    payload = _hourly(key)
    del payload["hourly"]["wind_speed_10m"]
    result = _source(lambda url, params: _response(200, payload)).forecast(
        latitude=37.5, longitude=127.0, at=target)
    assert result is not None
    assert result["wind_speed_kmh"] is None


def test_the_body_error_reader_passes_a_healthy_payload():
    """★오탐 방지 — 정상 응답을 오류로 읽으면 소스가 통째로 죽는다."""
    assert TravelSource._body_error({"hourly": {"time": []}}) is None
