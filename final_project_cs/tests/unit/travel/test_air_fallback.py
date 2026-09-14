# -*- coding: utf-8 -*-
"""대기질 대체 사슬 — 에어코리아가 멈춰도 **값을 낸다**, 모델 값이라는 사실은 숨기지 않는다.

☆2026-09-14 실측: 에어코리아가 첫 호출 뒤 연달아 `504 SERVICETIMEOUT_ERROR`(10.5초)를
  냈고, 대체가 없어 경복궁 점검이 치명이 됐다. Open-Meteo 응답 모양은 같은 날 실호출 그대로다.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.infrastructure.travel.air_quality import FallbackAir, MODEL_BASIS, OpenMeteoAir
from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 9, 14, 13, 20, tzinfo=KST)
PLACE = {"place_id": "p1", "latitude": 37.5796, "longitude": 126.977, "district": "종로구",
         "weather_sensitive": True}


def _model(pm10=(18.2, 12.7, 8.5), pm25=(13.9, 9.5, 6.5), status=200, payload=None):
    body = payload if payload is not None else {
        "latitude": 37.6, "longitude": 127.0,
        "hourly": {"time": ["2026-09-14T11:00", "2026-09-14T12:00", "2026-09-14T13:00"],
                   "pm10": list(pm10), "pm2_5": list(pm25)}}
    calls = []

    def transport(url, params):
        calls.append(dict(params))
        return httpx.Response(status, json=body, request=httpx.Request("GET", url))
    return OpenMeteoAir(transport=transport), calls


class _Dead:
    name = "airkorea"

    def at(self, **_):
        return None


# ── 모델 소스 ────────────────────────────────────────────────────
def test_the_model_value_for_the_item_hour_is_used_and_labelled_as_a_model():
    source, calls = _model()
    value = source.at(district="종로구", at=AT, latitude=37.5796, longitude=126.977)
    assert (value["pm10"], value["pm25"], value["data_time"]) == (8, 6, "2026-09-14T13:00")
    assert value["mode"] == "model" and value["basis"] == MODEL_BASIS
    assert value["pm10_grade"] is None and value["alert"] is None
    assert calls[0]["latitude"] == 37.58            # ★둘째 자리로 줄여 캐시를 나눠 쓴다


def test_a_model_value_over_the_threshold_raises_the_same_alert_shape():
    source, _ = _model(pm25=(0, 0, 80))
    value = source.at(at=AT, latitude=37.58, longitude=126.98)
    assert value["alert"] == {"level": "주의보", "pollutant": "초미세먼지(PM2.5)",
                              "value": 80, "limit": 75}


def test_an_hour_outside_the_returned_range_is_unknown_not_the_nearest_value():
    source, _ = _model()
    assert source.at(at=datetime(2026, 9, 20, 9, tzinfo=KST), latitude=37.58, longitude=126.98) is None
    assert source.misses["hour_out_of_range"] == 1


def test_an_open_meteo_error_body_is_unknown():
    """★`{"error": true}` 의 참/거짓 값은 공통 규칙(목록·사전)이 못 잡는다."""
    source, _ = _model(payload={"error": True, "reason": "Latitude must be in range"})
    assert source.at(at=AT, latitude=99.0, longitude=0.0) is None
    assert source.misses["body_error"] == 1


def test_no_coordinates_means_no_model_value():
    source, calls = _model()
    assert source.at(district="종로구", at=AT) is None and calls == []


# ── 사슬 + 점검 ──────────────────────────────────────────────────
def _check(air):
    return DisruptionCheck(TravelSources(air=air), limits=lambda: (60, 30),
                           quake_rules=lambda: (4.0, 100.0, 24.0)).check(place=PLACE, starts_at=AT)


def test_a_dead_airkorea_falls_back_to_the_model_instead_of_going_fatal():
    model, _ = _model()
    report = _check(FallbackAir([_Dead(), model]))
    air = next(c for c in report["checks"] if c["category"] == "air_quality")
    assert air["status"] == "ok" and air["source"] == "open_meteo_air"
    assert air["fell_back_from"] == ["airkorea"] and air["mode"] == "model"
    assert "air_quality" not in report["failed_categories"]


def test_a_model_alert_disruption_says_it_came_from_the_model():
    model, _ = _model(pm25=(0, 0, 160))
    report = _check(FallbackAir([_Dead(), model]))
    [d] = [d for d in report["disruptions"] if d["category"] == "air_quality"]
    assert d["mode"] == "model" and "모델" in d["basis"]


def test_when_every_air_source_fails_it_is_fatal_and_names_them_all():
    dead_model, _ = _model(status=504, payload={"x": 1})
    report = _check(FallbackAir([_Dead(), dead_model]))
    air = next(c for c in report["checks"] if c["category"] == "air_quality")
    assert report["verdict"] == "fatal"
    assert air["status"] == "failed" and air["tried"] == ["airkorea", "open_meteo_air"]


def test_a_place_without_a_district_still_gets_a_model_value_by_coordinates():
    model, _ = _model()
    report = DisruptionCheck(TravelSources(air=FallbackAir([_Dead(), model])),
                             limits=lambda: (60, 30), quake_rules=lambda: (4.0, 100.0, 24.0)
                             ).check(place={**PLACE, "district": None}, starts_at=AT)
    air = next(c for c in report["checks"] if c["category"] == "air_quality")
    assert air["status"] == "ok" and air["source"] == "open_meteo_air"
