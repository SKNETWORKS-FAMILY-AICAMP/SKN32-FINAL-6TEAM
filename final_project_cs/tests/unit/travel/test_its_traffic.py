# -*- coding: utf-8 -*-
"""ITS 돌발상황 — 무엇을 이상으로 세고, 무엇을 주의로만 두나.

★모든 표본은 2026-09-14 실호출(서울 122건·전국 474건)에서 본 모양 그대로다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck
from app.infrastructure.travel.its_traffic import KST, ItsTrafficEvents, classify, parse_message

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=KST)
PLACE = (37.5610, 126.9920)          # 남산1호터널 북측 인근


def _resp(status, payload):
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://x"))


def _ok(items):
    return {"header": {"resultCode": 0, "resultMsg": "SUCCESS"},
            "body": {"totalCount": len(items), "items": items}}


def _item(message, *, event="공사", detail="", road="삼일대로", lat=37.5612, lon=126.9922,
          start="20260622000000", end="20260930000000", road_type="시군도"):
    return {"type": road_type, "eventType": event, "eventDetailType": detail,
            "startDate": start, "endDate": end, "coordX": str(lon), "coordY": str(lat),
            "roadName": road, "roadNo": "0", "lanesBlockType": "", "lanesBlocked": "",
            "message": message, "linkId": "1", "roadDrcType": ""}


PARTIAL = "<공사>::삼일대로::남산1호터널북측::남산한옥마을::4차로::[공사/통제] 남산1호터널"
FULL = "<공사>::도림천로::신도림고가차도::도림교앞교차로::진행방향 전체차로::[공사/통제] 전면"
RALLY = "<공사>::강남순환로::금천TG::선암TG::1차로::[집회]장소 : 강남순환로"


def _source(items, *, status=200):
    payload = _ok(items) if status == 200 else {
        "header": {"resultCode": 4005, "resultMsg": "유효하지 않은 인증키입니다."}, "body": ""}
    return ItsTrafficEvents(service_key="k", now=lambda: NOW,
                            transport=lambda url, params: _resp(status, payload))


# ── 메시지 펴기 · 분류 ──────────────────────────────────────────
def test_the_real_message_shape_is_parsed():
    parsed = parse_message(PARTIAL)
    assert parsed["lanes"] == "4차로" and parsed["tags"] == ["공사", "통제"]
    assert parsed["section"] == "남산1호터널북측 → 남산한옥마을"


def test_the_ubiquitous_control_tag_alone_is_only_an_advisory():
    """★108/122 건에 [공사/통제] 가 붙어 있다. 「통제」 낱말로 이상을 세면 거의 전부가 된다."""
    assert classify(_item(PARTIAL))[0] == "advisory"


@pytest.mark.parametrize("item,reason", [
    (_item(FULL), "전체 차로 통제"),
    (_item(RALLY), "집회·행사 집회"),
    (_item("<기타>::x::a::b::1차로::홍보", event="기타", detail="이벤트/홍보"), "집회·행사 이벤트/홍보"),
    (_item("<사고>::x::a::b::1차로::추돌", event="교통사고"), "교통사고"),
])
def test_blocking_events_are_disruptions(item, reason):
    assert classify(item) == ("disruption", reason)


# ── 거리 · 시각 ─────────────────────────────────────────────────
def test_only_events_within_the_radius_count():
    far = _item(FULL, lat=37.60, lon=127.05)
    result = _source([_item(FULL), far]).near(latitude=PLACE[0], longitude=PLACE[1], at=NOW)
    assert len(result["for_place"]) == 1 and result["for_place"][0]["distance_m"] < 100
    assert result["total_in_box"] == 2


def test_an_event_that_ended_before_the_time_does_not_count():
    ended = _item(FULL, start="20260901000000", end="20260910000000")
    assert _source([ended]).near(latitude=PLACE[0], longitude=PLACE[1], at=NOW)["for_place"] == []


def test_an_open_ended_accident_is_not_stretched_into_tomorrow():
    """★지금 난 사고가 내일 일정까지 이어진다고 보지 않는다."""
    accident = _item("<사고>::x::a::b::1차로::추돌", event="교통사고",
                     start="20260914115000", end="")
    src = _source([accident])
    assert src.near(latitude=PLACE[0], longitude=PLACE[1], at=NOW + timedelta(hours=1))["for_place"]
    assert src.near(latitude=PLACE[0], longitude=PLACE[1], at=NOW + timedelta(days=1))["for_place"] == []


# ── 실패 · 빈 결과 ─────────────────────────────────────────────
def test_a_bad_key_is_a_counted_miss_not_no_events():
    """★실측: 틀린 키 → HTTP 401 · resultCode 4005. 「돌발 없음」과 섞지 않는다."""
    src = _source([], status=401)
    assert src.near(latitude=PLACE[0], longitude=PLACE[1], at=NOW) is None
    assert src.misses["http_401"] == 1


def test_no_events_in_the_box_is_a_known_empty_list():
    result = _source([]).near(latitude=PLACE[0], longitude=PLACE[1], at=NOW)
    assert result["for_place"] == [] and result["advisories"] == []


# ── 점검에 들어가면 ──────────────────────────────────────────────
def _report(items, *, sensitive=False, lat=PLACE[0]):
    place = {"place_id": "p", "latitude": lat, "longitude": PLACE[1], "weather_sensitive": sensitive}
    return DisruptionCheck(TravelSources(traffic=_source(items)),
                           limits=lambda: (60, 30)).check(place=place, starts_at=NOW)


def _traffic(report):
    return next(c for c in report["checks"] if c["category"] == "traffic_control")


def test_even_an_indoor_place_is_disrupted_when_the_road_is_closed():
    report = _report([_item(FULL)])
    assert report["verdict"] == "disrupted"
    assert report["disruptions"][0]["kind"] == "전체 차로 통제"


def test_partial_lane_work_is_an_advisory_and_the_utic_gap_is_stated():
    report = _report([_item(PARTIAL)])
    assert report["verdict"] == "clear"
    assert report["advisories"][0]["field"] == "partial_lane"
    assert "UTIC" in _traffic(report)["note"]


def test_missing_coordinates_fail_the_traffic_check():
    report = _report([], lat=None)
    assert _traffic(report)["status"] == "failed" and report["verdict"] == "fatal"
