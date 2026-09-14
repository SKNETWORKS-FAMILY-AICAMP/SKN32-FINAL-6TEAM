# -*- coding: utf-8 -*-
"""UTIC 돌발정보 · ITS 와 합치기 — 모양은 2026-09-14 실호출 그대로다. 네트워크는 안 탄다."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck
from app.infrastructure.travel.traffic_chain import CombinedTraffic
from app.infrastructure.travel.utic import UticIncidents, classify, title_tags

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 14, 16, 0, tzinfo=KST)
#: 실측 레코드(여의도 올림픽대로 사고)의 좌표 근처
PLACE = {"place_id": "p1", "latitude": 37.5180, "longitude": 126.9470, "weather_sensitive": False}


def _record(title="[사고] 올림픽대로 동작대교JC 에서 여의상류IC 방향 차로 차량사고 , [차량사고] 올림픽대로",
            x="126.94657176", y="37.51771677521985", start="2026년 09월 14일  15시 35분",
            end="2026년 09월 14일  16시 24분", lane="차로", incident_id="L90173419309"):
    return (f"<record><incidentId>{incident_id}</incidentId><incidenteTypeCd>1</incidenteTypeCd>"
            f"<addressJibun>서울 영등포구 여의도동 87-5</addressJibun>"
            f"<locationDataX>{x}</locationDataX><locationDataY>{y}</locationDataY>"
            f"<incidentTitle>{title}</incidentTitle><startDate>{start}</startDate>"
            f"<endDate>{end}</endDate><lane>{lane}</lane><roadName>올림픽대로</roadName>"
            f"<controlType>0</controlType></record>")


def _source(*records, text=None, status=200):
    body = text if text is not None else (
        '<?xml version="1.0" encoding="utf-8" ?> <result>' + "".join(records) + "</result>")
    calls = []

    def transport(url, params):
        calls.append(dict(params))
        return httpx.Response(status, text=body, request=httpx.Request("GET", url))
    return UticIncidents(service_key="k1", transport=transport, now=lambda: NOW), calls


# ── 분류 ─────────────────────────────────────────────────────────
def test_title_tags_are_split_out():
    assert title_tags("[사고] 올림픽대로 … [차량사고] …") == ["사고", "차량사고"]
    assert title_tags("[공사/통제] 세종대로") == ["공사", "통제"]


def test_classification_follows_the_its_rules():
    assert classify({"incidentTitle": "[사고] 강변북로"})[0] == "disruption"
    assert classify({"incidentTitle": "[집회] 세종대로 일대"}) == ("disruption", "집회·행사 집회")
    assert classify({"incidentTitle": "[공사] 한강대교", "lane": "전체차로"})[0] == "disruption"
    # ★「통제」 낱말만으로는 이상이 아니다 — ITS 에서 [공사/통제] 가 대부분이었다
    assert classify({"incidentTitle": "[공사/통제] 한강대교", "lane": "1차로"})[0] == "advisory"


# ── 어댑터 ───────────────────────────────────────────────────────
def test_a_nearby_accident_in_progress_is_a_disruption():
    source, calls = _source(_record())
    value = source.near(latitude=PLACE["latitude"], longitude=PLACE["longitude"], at=NOW)
    [hit] = value["for_place"]
    assert hit["reason"] == "교통사고" and hit["distance_m"] < 200
    assert hit["starts_at"] == "2026-09-14T15:35:00+09:00"
    assert calls == [{"key": "k1"}] and value["source"] == "utic"


def test_far_or_finished_incidents_do_not_count():
    far, _ = _source(_record(x="129.0", y="35.1"))
    assert far.near(latitude=37.518, longitude=126.947, at=NOW)["for_place"] == []
    finished, _ = _source(_record())
    after = NOW + timedelta(hours=1)          # 16:24 에 끝났다
    assert finished.near(latitude=37.518, longitude=126.947, at=after)["for_place"] == []


def test_the_ip_error_json_is_unknown_not_no_incident():
    """★등록 안 된 IP 면 200 에 JSON 오류가 온다(실측). 「돌발 없음」으로 읽으면 안 된다."""
    source, _ = _source(text='[{"resultCode":"03","resultMsg":"허용된 IP가 아닙니다."}]')
    assert source.near(latitude=37.518, longitude=126.947, at=NOW) is None
    assert source.misses["not_xml"] == 1


def test_broken_xml_is_unknown():
    source, _ = _source(text="<result><record>")
    assert source.near(latitude=37.518, longitude=126.947, at=NOW) is None


# ── 합치기 ───────────────────────────────────────────────────────
class _Fixed:
    def __init__(self, name, value):
        self.name, self.value = name, value

    def near(self, **_):
        return self.value


def _its(items=()):
    return _Fixed("its", {"for_place": list(items), "advisories": [], "source": "its",
                          "confirmed_at": "2026-09-14T06:00:00+00:00"})


def test_both_sources_are_merged_and_each_line_says_where_it_came_from():
    utic, _ = _source(_record())
    combined = CombinedTraffic([_its([{"reason": "전체 차로 통제", "road": "강변북로"}]), utic])
    value = combined.near(latitude=37.518, longitude=126.947, at=NOW)
    assert [(i["reason"], i["source"]) for i in value["for_place"]] == [
        ("전체 차로 통제", "its"), ("교통사고", "utic")]
    assert value["sources"] == ["its", "utic"] and value["partial_from"] == []


def test_one_source_down_still_answers_but_says_so():
    utic, _ = _source(_record())
    value = CombinedTraffic([_Fixed("its", None), utic]).near(
        latitude=37.518, longitude=126.947, at=NOW)
    assert value["sources"] == ["utic"] and value["partial_from"] == ["its"]


def test_both_down_is_unknown():
    assert CombinedTraffic([_Fixed("its", None), _Fixed("utic", None)]).near(
        latitude=37.5, longitude=127.0, at=NOW) is None


# ── 점검 ─────────────────────────────────────────────────────────
def _check(traffic):
    return DisruptionCheck(TravelSources(traffic=traffic), limits=lambda: (60, 30),
                           quake_rules=lambda: (4.0, 100.0, 24.0)).check(place=PLACE, starts_at=NOW)


def test_a_utic_accident_disrupts_the_item_through_the_check():
    utic, _ = _source(_record())
    report = _check(CombinedTraffic([_its(), utic]))
    [d] = [d for d in report["disruptions"] if d["category"] == "traffic_control"]
    assert d["kind"] == "교통사고" and d["source"] == "utic"
    check = next(c for c in report["checks"] if c["category"] == "traffic_control")
    assert "note" not in check


def test_when_utic_is_down_the_check_says_rallies_may_be_missed():
    report = _check(CombinedTraffic([_its(), _Fixed("utic", None)]))
    check = next(c for c in report["checks"] if c["category"] == "traffic_control")
    assert check["status"] == "ok" and check["partial_from"] == ["utic"]
    assert "UTIC" in check["note"]
    assert "traffic_control" not in report["failed_categories"]


def test_when_every_traffic_source_fails_it_is_fatal_and_names_them():
    report = _check(CombinedTraffic([_Fixed("its", None), _Fixed("utic", None)]))
    check = next(c for c in report["checks"] if c["category"] == "traffic_control")
    assert report["verdict"] == "fatal" and check["tried"] == ["its", "utic"]
