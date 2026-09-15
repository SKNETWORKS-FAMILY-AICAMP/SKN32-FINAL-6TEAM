# -*- coding: utf-8 -*-
"""기상청 지진정보 — 「지진 없음」과 「모름」을 가르고, 거리·규모로만 판정하는가.

★공급자 응답 모양은 2026-09-14 실호출 그대로다. 네트워크는 안 탄다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck
from app.infrastructure.travel.kma_earthquake import KmaEarthquakeSource, parse_event

KST = ZoneInfo("Asia/Seoul")
#: 실측 항목(2026-09-12 인도네시아 해역)
REAL_ITEM = {"cnt": 1, "fcTp": 2, "inT": "", "lat": -5.09, "loc": "인도네시아 자카르타 북쪽 125km 해역",
             "lon": 106.9, "mt": 6.6, "rem": "국내영향없음. \n발생시각, 규모, 발생위치, 발생깊이는 "
             "미국지질조사소(USGS) 분석결과임.", "stnId": 108, "tmEqk": 20260912062355,
             "tmFc": 202609120645, "tmSeq": 1081, "dep": 359}
SEOUL = {"place_id": "p1", "latitude": 37.58, "longitude": 126.98, "weather_sensitive": False}
RULES = lambda: (4.0, 100.0, 24.0)   # noqa: E731


def _resp(payload) -> httpx.Response:
    return httpx.Response(200, json=payload, request=httpx.Request("GET", "https://x"))


def _source(payload) -> KmaEarthquakeSource:
    return KmaEarthquakeSource(service_key="k", transport=lambda url, params: _resp(payload))


def _ok(items):
    return {"response": {"header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
                         "body": {"items": {"item": items}}}}


WINDOW = (datetime(2026, 9, 11, 12, tzinfo=KST), datetime(2026, 9, 12, 12, tzinfo=KST))


# ── 어댑터 ───────────────────────────────────────────────────────
def test_no_data_code_means_no_earthquake_not_unknown():
    """★`03 NO_DATA` 는 지진이 없는 날의 실제 응답이다(09-13·09-14 실측). 모름이 아니다."""
    value = _source({"response": {"header": {"resultCode": "03", "resultMsg": "NO_DATA"}}}).recent(
        since=WINDOW[0], until=WINDOW[1])
    assert value is not None and value["events"] == []


def test_any_other_error_code_is_unknown():
    source = _source({"response": {"header": {"resultCode": "99", "resultMsg": "최대 조회 기간 초과"}}})
    assert source.recent(since=WINDOW[0], until=WINDOW[1]) is None


def test_the_real_item_shape_parses():
    event = parse_event(REAL_ITEM)
    assert event["magnitude"] == 6.6 and event["depth_km"] == 359.0
    assert event["at"] == "2026-09-12T06:23:55+09:00"
    assert event["intensity"] is None and event["remark"].startswith("국내영향없음")


def test_a_single_unreadable_item_makes_the_whole_list_unknown():
    """★못 읽은 항목이 가까운 강진일 수 있다 — 빼고 「없음」이라 하지 않는다."""
    broken = {**REAL_ITEM, "lat": None}
    assert _source(_ok([REAL_ITEM, broken])).recent(since=WINDOW[0], until=WINDOW[1]) is None


def test_events_outside_the_time_window_are_dropped():
    old = {**REAL_ITEM, "tmEqk": 20260910010000}
    value = _source(_ok([REAL_ITEM, old])).recent(since=WINDOW[0], until=WINDOW[1])
    assert [e["at"] for e in value["events"]] == ["2026-09-12T06:23:55+09:00"]


# ── 판정 ─────────────────────────────────────────────────────────
class _Quake:
    name = "kma_earthquake"

    def __init__(self, value):
        self.value, self.windows = value, []

    def recent(self, *, since, until):
        self.windows.append((since, until))
        return self.value


def _event(magnitude, lat, lon, location="서울 근처"):
    return {"at": "2026-09-15T10:00:00+09:00", "latitude": lat, "longitude": lon,
            "magnitude": magnitude, "location": location, "intensity": None}


def _check(value, place=SEOUL, at=datetime(2026, 9, 15, 14, tzinfo=KST)):
    source = _Quake(None if value is None else {"events": value, "source": "kma_earthquake",
                                                "confirmed_at": "x", "window": {}})
    report = DisruptionCheck(TravelSources(earthquake=source), limits=lambda: (60, 30),
                             quake_rules=RULES).check(place=place, starts_at=at)
    return report, source


def test_a_strong_nearby_quake_disrupts_even_an_indoor_place():
    report, _ = _check([_event(4.5, 37.40, 127.10)])          # 약 22km
    assert report["verdict"] == "disrupted"
    [d] = [d for d in report["disruptions"] if d["category"] == "earthquake"]
    assert d["kind"] == "규모 4.5 지진" and d["distance_km"] < 30


def test_a_weak_nearby_quake_is_only_an_advisory():
    report, _ = _check([_event(2.5, 37.40, 127.10)])
    assert report["verdict"] == "clear"
    assert [a["field"] for a in report["advisories"] if a["category"] == "earthquake"] == ["magnitude"]


def test_a_far_strong_quake_is_ignored():
    """실측 항목(인도네시아 규모 6.6) — 반경 밖이라 이상도 주의도 아니다."""
    report, _ = _check([parse_event(REAL_ITEM)])
    quake = next(c for c in report["checks"] if c["category"] == "earthquake")
    assert quake["status"] == "ok" and report["verdict"] == "clear"
    assert not [a for a in report["advisories"] if a["category"] == "earthquake"]


def test_a_failed_lookup_is_fatal():
    report, _ = _check(None)
    assert report["verdict"] == "fatal" and report["failed_categories"] == ["earthquake"]


def test_a_future_item_is_only_checked_up_to_now():
    """★아직 안 난 지진은 없다 — 창의 끝은 일정 시각과 지금 중 이른 쪽."""
    future = datetime.now(KST) + timedelta(days=2)
    _, source = _check([], at=future)
    since, until = source.windows[0]
    assert until <= datetime.now(KST) + timedelta(seconds=5)
    assert until - since == timedelta(hours=24)


def test_a_missing_source_is_unconnected_with_its_reason():
    sources = TravelSources(unavailable={"earthquake": "키 없음"})
    report = DisruptionCheck(sources, limits=lambda: (60, 30), quake_rules=RULES).check(
        place=SEOUL, starts_at=None)
    quake = next(c for c in report["checks"] if c["category"] == "earthquake")
    assert quake == {"category": "earthquake", "status": "not_connected", "reason": "키 없음"}
