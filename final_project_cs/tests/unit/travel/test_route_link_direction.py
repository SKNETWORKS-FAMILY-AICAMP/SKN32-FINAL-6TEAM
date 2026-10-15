# -*- coding: utf-8 -*-
"""도로 사건의 **구간·방향** 대조 `[2026-10-13]` — 도로명만 맞는 반대 방향 사건을 경로 사건으로 세지 않는다.

서울 실경보 28건 재생에서 반대 방향 시험이 2/20 이었다(도로명 전용 대조라 방향을 못 가렸다).
경로 후보가 도로 구간 번호(`링크:`)를 실으면 사건 원문의 구간 번호와 겹칠 때만 걸린다.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.domains.travel_ops.components.itinerary.itinerary_changes import option_hits
from app.domains.travel_ops.components.itinerary.route_uses import problem
from app.domains.travel_ops.ports.data_sources.utic import UticIncidents, UticRouteEvents

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 23, 17, 10, tzinfo=KST)
FORWARD, REVERSE, OTHER = "1220001100", "1220001200", "1220009900"


def _record(incident, title, *, road="올림픽대로", lane="1차로", links=FORWARD):
    return (f"<record><incidentId>{incident}</incidentId><locationDataX>126.9</locationDataX>"
            f"<locationDataY>37.55</locationDataY><incidentTitle>{title}</incidentTitle>"
            f"<startDate>2026년 09월 23일  17시 00분</startDate><endDate>2026년 09월 23일  20시 00분</endDate>"
            f"<lane>{lane}</lane><roadName>{road}</roadName><linkId>{links}</linkId></record>")


def _events(*records):
    body = "<result>" + "".join(records) + "</result>"
    source = UticIncidents(service_key="k", now=lambda: NOW, transport=lambda url, params:
                           httpx.Response(200, text=body, request=httpx.Request("GET", url)))
    return UticRouteEvents(source)


def _hits(source, uses):
    return option_hits({"id": "taxi", "uses": uses}, source.affecting(uses, NOW))


ONE_WAY = "[사고] 올림픽대로 월드컵대교 에서 가양대교 방향 1차로 교통사고"
BOTH_WAYS = "[행사] 올림픽대로 A 에서 B 방향 양방향 전체차로 축제"


def test_same_direction_link_is_a_verified_hit():
    hits = _hits(_events(_record("L1", ONE_WAY)), ["도로:올림픽대로", f"링크:{FORWARD}"])
    assert list(hits) == [f"링크:{FORWARD}"]
    assert hits[f"링크:{FORWARD}"]["route_match"] == {"status": "link_overlap", "basis": "provider_link_id",
                                                      "link_id": FORWARD}


def test_opposite_direction_one_way_incident_does_not_hit():
    assert _hits(_events(_record("L1", ONE_WAY)), ["도로:올림픽대로", f"링크:{REVERSE}"]) == {}


def test_both_way_incident_stays_a_road_candidate_without_link_overlap():
    hits = _hits(_events(_record("L2", BOTH_WAYS, lane="양방향 전체차로")), ["도로:올림픽대로", f"링크:{REVERSE}"])
    assert list(hits) == ["도로:올림픽대로"]
    assert hits["도로:올림픽대로"]["route_match"]["status"] == "unverified"
    assert hits["도로:올림픽대로"]["both_directions"] is True


def test_route_without_links_keeps_the_old_road_name_candidate():
    hits = _hits(_events(_record("L1", ONE_WAY)), ["도로:올림픽대로"])
    assert hits["도로:올림픽대로"]["route_match"] == {"status": "unverified", "basis": "road_name_only"}


def test_unknown_incident_links_are_not_turned_into_no_event():
    """사건 쪽 구간 번호를 모르면 도로명 후보로 남긴다 — 모르는 것을 「안 걸림」으로 바꾸지 않는다."""
    hits = _hits(_events(_record("L3", ONE_WAY, links="")), ["도로:올림픽대로", f"링크:{REVERSE}"])
    assert list(hits) == ["도로:올림픽대로"]


def test_a_one_way_incident_does_not_hide_a_both_way_incident_on_the_same_road():
    source = _events(_record("L1", ONE_WAY, links=OTHER), _record("L2", BOTH_WAYS, lane="양방향 전체차로"))
    hits = _hits(source, ["도로:올림픽대로", f"링크:{REVERSE}"])
    assert hits["도로:올림픽대로"]["incident_id"] == "L2"


def test_link_targets_are_supported_and_shape_checked():
    source = _events()
    assert source.unsupported([f"링크:{FORWARD}", "도로:올림픽대로", "3호선:경복궁"]) == ["3호선:경복궁"]
    assert problem(f"링크:{FORWARD}") is None
    assert problem("링크:올림픽대로") is not None
    assert problem("링크:12") is not None


def test_link_only_route_from_the_taxi_planner():
    """택시 후보는 도로 이름 없이 `링크:` 만 싣는다(이동 계산 2026-10-13). 같은 방향 구간이면 걸리고 반대 방향 한 방향 사건은 안 걸린다."""
    source = _events(_record("L1", ONE_WAY))
    assert list(_hits(source, [f"링크:{FORWARD}"])) == [f"링크:{FORWARD}"]
    assert _hits(source, [f"링크:{REVERSE}"]) == {}


def test_link_only_route_misses_a_both_way_incident_on_the_other_side_known_limit():
    """알려진 한계 — 원문이 한 방향 번호만 실은 양방향 통제는 반대쪽 구간만 지나는 `링크:` 전용 후보에서 못 잡는다(반대 방향 번호 자료 없음)."""
    source = _events(_record("L2", BOTH_WAYS, lane="양방향 전체차로"))
    assert _hits(source, [f"링크:{REVERSE}"]) == {}
