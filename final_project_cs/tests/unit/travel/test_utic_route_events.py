# -*- coding: utf-8 -*-
"""UTIC 로 감시 루프의 **경로 사건**(도로 통제)을 답한다 — 이동-A6 의 실제 소스 판.

★지하철 무정차는 소스가 없다 — 「사건 없음」이 아니라 「확인 못 한 대상」으로 드러나는가.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

from app.infrastructure.travel.utic import UticIncidents, UticRouteEvents
from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.trip_watch import TripTickResult, TripWatcher

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 23, 17, 10, tzinfo=KST)


def _record(title, road="세종대로", start="2026년 09월 23일  17시 00분",
            end="2026년 09월 23일  20시 00분", lane="차로"):
    return (f"<record><incidentId>X1</incidentId><locationDataX>126.9769</locationDataX>"
            f"<locationDataY>37.5700</locationDataY><incidentTitle>{title}</incidentTitle>"
            f"<startDate>{start}</startDate><endDate>{end}</endDate><lane>{lane}</lane>"
            f"<roadName>{road}</roadName></record>")


def _events(*records, text=None):
    body = text if text is not None else "<result>" + "".join(records) + "</result>"
    source = UticIncidents(service_key="k", now=lambda: NOW, transport=lambda url, params:
                           httpx.Response(200, text=body, request=httpx.Request("GET", url)))
    return UticRouteEvents(source)


def test_a_rally_on_the_road_becomes_a_road_control_event():
    events = _events(_record("[집회] 세종대로 광화문 일대"))
    found = events.affecting(["도로:세종대로", "3호선:경복궁"])
    assert list(found) == ["도로:세종대로"]
    assert found["도로:세종대로"]["effect"] == "road_control"
    assert "세종대로" in found["도로:세종대로"]["summary"] and found["도로:세종대로"]["source"] == "utic"


def test_partial_lane_works_and_finished_incidents_do_not_cut_the_route():
    events = _events(_record("[공사] 세종대로 1차로", lane="1차로"),
                     _record("[사고] 세종대로", end="2026년 09월 23일  16시 00분"))
    assert events.affecting(["도로:세종대로"]) == {}


def test_subway_targets_are_reported_as_unchecked_not_as_no_event():
    events = _events()
    assert events.unsupported(["3호선:경복궁", "도로:세종대로", "도보:서울역"]) == [
        "3호선:경복궁", "도보:서울역"]
    assert events.affecting(["3호선:경복궁"]) == {}


def test_an_unreadable_utic_is_unknown():
    events = _events(text='[{"resultCode":"03","resultMsg":"허용된 IP가 아닙니다."}]')
    assert events.affecting(["도로:세종대로"]) is None


# ── 감시 루프 ────────────────────────────────────────────────────
ROUTE = {"from": "경복궁", "to": "서울역", "planned": "bus", "options": [
    {"id": "bus", "label": "세종대로 버스", "eta_min": 20, "eta_min_if_controlled": 55,
     "walk_m": 200, "fare_krw": 1500, "uses": ["도로:세종대로"]},
    {"id": "subway", "label": "지하철", "eta_min": 28, "walk_m": 450, "fare_krw": 1500,
     "uses": ["3호선:경복궁", "4호선:서울역"]}]}


def _item():
    return Item(item_id=uuid4(), seq=8, kind="mobility", title="경복궁 → 서울역", place_id=None,
                starts_at=NOW + timedelta(minutes=5), ends_at=NOW + timedelta(minutes=35),
                detail={"route": "r1", "route_def": ROUTE})


def _watcher(route_events):
    return TripWatcher(store=None, check=lambda **_: {}, connection_factory=lambda: None,
                       clock=lambda: NOW, route_events=route_events)


def test_an_unreadable_route_source_makes_the_item_fatal_not_quiet():
    result = TripTickResult()
    _watcher(_events(text="not xml"))._check_route(uuid4(), _item(), NOW, result)
    assert len(result.fatal) == 1
    assert result.fatal[0]["report"]["failed_categories"] == ["route_events"]


def test_a_planned_subway_route_is_counted_as_unchecked():
    item = _item()
    item.detail = {**item.detail, "option": "subway"}
    result = TripTickResult()
    _watcher(_events())._check_route(uuid4(), item, NOW, result)
    assert result.unchecked == [{"trip_id": result.unchecked[0]["trip_id"], "item": item.title,
                                 "targets": ["3호선:경복궁", "4호선:서울역"]}]
    assert result.fatal == [] and result.adjusted == []
