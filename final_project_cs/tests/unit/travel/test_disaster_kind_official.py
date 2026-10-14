# -*- coding: utf-8 -*-
"""재난 문자 재해구분 공식 목록 41종 — 이름마다 갈래가 하나씩 정해져 있다 `[2026-10-13 사용자 승인]`.

목록 출처: 국민안전24 재난문자 조회 화면(`wiki/records/reports/2026-10-13_재난문자_재해구분_공식목록.md`).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.planning.safety import SafetyRules, _from_message
from app.domains.travel_ops.ports.data_sources import disaster_msg, notice_impact
from app.domains.travel_ops.ports.data_sources.disaster_msg import (
    OFFICIAL_KINDS, PLACE_KINDS, RECORD_ONLY_KINDS, WEATHER_KINDS, judge)

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 10, 13, 9, 0, tzinfo=KST)


@pytest.fixture(autouse=True)
def _reset():
    yield
    notice_impact.set_second_opinion(None)
    disaster_msg.set_excluded_sink(None)


def _row(text, kind):
    return {"created_at": AT, "kind": kind, "step": "안전안내", "regions": ["서울특별시 종로구 청운효자동"], "text": text, "serial": 1}


def _judge(*rows):
    return judge(list(rows), region="서울", district="종로구", window_start=AT, at=AT)


def test_official_list_has_41_kinds_and_every_one_has_a_branch():
    assert len(OFFICIAL_KINDS) == 41
    branches = [WEATHER_KINDS & OFFICIAL_KINDS, PLACE_KINDS & OFFICIAL_KINDS, RECORD_ONLY_KINDS, {"기타"}]
    assert set().union(*branches) == OFFICIAL_KINDS
    assert sum(len(b) for b in branches) == 41                     # 한 이름이 두 갈래에 들어가지 않는다


def test_old_civil_defense_name_is_replaced_by_the_official_one():
    assert "민방공" in PLACE_KINDS and "민방위" not in PLACE_KINDS and "민방위" not in OFFICIAL_KINDS


@pytest.mark.parametrize("kind", ["안개", "미세먼지", "대조기"])
def test_new_weather_kinds_go_only_to_weather_sensitive_places(kind):
    messages, unclassified = _judge(_row("시정 100m 미만, 운전과 야외활동에 유의 바랍니다", kind))
    assert len(messages) == 1 and messages[0]["weather"] is True and unclassified == []


@pytest.mark.parametrize("kind", ["교통사고", "교통", "환경오염사고", "화생방사고", "폭동", "비상사태", "민방공"])
def test_new_place_kinds_are_sent_by_name_for_every_place(kind):
    messages, unclassified = _judge(_row("인근 주민은 안전에 유의 바랍니다", kind))
    assert len(messages) == 1 and messages[0]["weather"] is False and unclassified == []


def test_record_only_kind_without_impact_goes_to_the_record_not_to_unknown():
    seen = []
    disaster_msg.set_excluded_sink(seen.append)
    messages, unclassified = _judge(_row("말라리아 경보 발령. 야간 외출 시 긴 옷을 입어 모기에 물리지 않게 주의 바랍니다", "전염병"))
    assert messages == [] and unclassified == []                   # 「알아보지 못한 구분」이 아니다
    assert len(seen) == 1 and seen[0]["kind"] == "전염병"


def test_record_only_kind_is_still_sent_when_the_text_shows_travel_impact():
    messages, _ = _judge(_row("서울 시내버스 파업으로 오늘 첫차부터 시내버스 운행 중단, 지하철을 이용 바랍니다.", "통신"))
    assert len(messages) == 1 and messages[0]["impact"] == "bus"


def test_kind_outside_the_official_list_is_judged_by_text_and_warned(caplog):
    disaster_msg._warned_new_kinds.discard("새재난")
    with caplog.at_level("WARNING"):
        messages, unclassified = _judge(_row("설 연휴 문 여는 병의원은 응급의료포털에서 확인하세요", "새재난"),
                                        _row("설 연휴 문 여는 약국은 응급의료포털에서 확인하세요", "새재난"))
    assert messages == [] and len(unclassified) == 2
    assert sum("새재난" in r.getMessage() for r in caplog.records) == 1  # 같은 이름은 한 번만 경고한다


def _rules():
    return SafetyRules(pause_enabled=True, day_steps=frozenset({"긴급재난", "위급재난"}), day_kinds=frozenset({"민방공", "지진"}),
                       trip_steps=frozenset({"위급재난"}), trip_kinds=frozenset({"화산", "테러", "원전", "방사능"}),
                       trip_keywords=("공습경보", "경계경보"), exclude_keywords=("훈련",), trip_magnitude_min=6.0)


def test_civil_defense_balloon_notice_does_not_stop_the_whole_trip():
    event = _from_message({"kind": "민방공", "step": "긴급재난", "text": "북한 대남 오물풍선 부양 중. 낙하물 발견 시 접촉하지 말고 신고 바랍니다"}, _rules())
    assert event is not None and event.level == "day"


def test_civil_defense_air_raid_alert_still_stops_the_whole_trip():
    event = _from_message({"kind": "민방공", "step": "긴급재난", "text": "서울 지역 경계경보 발령. 대피할 준비를 하시기 바랍니다"}, _rules())
    assert event is not None and event.level == "trip"
