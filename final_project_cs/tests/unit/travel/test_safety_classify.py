# -*- coding: utf-8 -*-
"""재난 시 일정 정지 — 어떤 사건이 「그날 정지」이고 어떤 사건이 「여행 전체 정지」인가. `[결정 2026-10-06 사용자]`

★지키려는 것
 ①지진 · 긴급재난 이상의 몸이 위험한 재난 → **그날 정지**. 전쟁 · 공습 · 활화산 같은 심각한 사건 → **여행 전체 정지**(둘이 함께 오면 전체가 앞선다)
 ②**일상 문자는 정지하지 않는다** — 안전안내 단계 · 날씨 재해(호우 · 폭염) · 교통통제 · 실종. 훈련 · 해제 문자도 정지하지 않는다
 ③재해구분이 **모르는 값이어도** 본문의 심각 낱말(공습경보 · 화산 …)로 가른다 — 전쟁이 「기타」로 와도 놓치지 않는다
 ④규모를 모르는 지진은 정지하지 않는다(지어내지 않는다). 지진은 규모가 크면 여행 전체
 ⑤대피 장소 종류: 지진 → 옥외대피장소, 전쟁 · 폭발 · 테러 · 화산 → 민방위 대피시설, 화재 · 산불 → 목록 없이 공식 안내만
 ⑥끄면(`pause_enabled: false`) 아무것도 정지하지 않는다

재현:

    python -m pytest tests/unit/travel/test_safety_classify.py -v
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.planning.safety import SafetyRules, classify

RULES = SafetyRules(pause_enabled=True, day_steps=frozenset({"긴급재난", "위급재난"}),
                    day_kinds=frozenset({"지진", "지진해일", "화재", "산불", "붕괴", "폭발", "테러", "화산", "민방위", "원전", "방사능", "가스"}),
                    trip_steps=frozenset({"위급재난"}), trip_kinds=frozenset({"민방위", "화산", "테러", "원전", "방사능"}),
                    trip_keywords=("공습경보", "경계경보", "화산", "분화", "전쟁", "미사일", "방사능", "생화학"),
                    trip_magnitude_min=6.0, exclude_keywords=("훈련", "해제", "실제 상황이 아"))


def _msg(kind, step, text="본문", at="2026-09-23T10:07:00+09:00"):
    return {"category": "disaster_msg", "kind": kind, "step": step, "text": text, "created_at": at}


def _quake(magnitude=5.1):
    return {"category": "earthquake", "magnitude": magnitude, "distance_km": 12.0, "location": "서울 북서쪽 5km 지역", "at": "2026-09-23T10:05:00+09:00"}


def _level(*causes, rules=RULES):
    event = classify(list(causes), rules)
    return None if event is None else event.level


@pytest.mark.parametrize("cause,expected", [
    (_quake(4.1), "day"), (_quake(5.9), "day"), (_quake(6.0), "trip"), (_quake(7.2), "trip"),        # ①지진 — 규모로 갈린다
    (_msg("지진", "긴급재난"), "day"), (_msg("화재", "긴급재난"), "day"), (_msg("산불", "긴급재난"), "day"),
    (_msg("민방위", "위급재난", "공습경보가 발령되었습니다"), "trip"),                                  # ①전쟁 — 여행 전체
    (_msg("화산", "긴급재난", "백두산 화산 분화"), "trip"),                                             # ①활화산 — 낱말이 있어 전체
    (_msg("기타", "긴급재난", "서울 전역에 공습경보가 발령되었습니다"), "trip"),                         # ③모르는 구분(기타)도 낱말로 잡는다
    (_msg("새재해", "위급재난", "알 수 없는 위급 상황"), "trip"),                                      # ③모르는 구분 + 위급재난 = 전체
])
def test_what_stops_the_day_and_what_stops_the_whole_trip(cause, expected):
    assert _level(cause) == expected


@pytest.mark.parametrize("cause", [
    _msg("지진", "안전안내"),                                    # ②안전안내 단계는 일상 문자다
    _msg("호우", "긴급재난", "호우경보"), _msg("폭염", "긴급재난"), _msg("태풍", "위급재난", "태풍 상륙"),   # ②날씨 재해는 정지가 아니다(기존 실내 대체 · 안전 알림) — 위급재난이어도
    _msg("교통통제", "안전안내", "도로 통제"), _msg("기타", "안전안내", "실종자를 찾습니다"),
    _msg("민방위", "위급재난", "오늘 14시 민방위 훈련 공습경보 발령 — 실제 상황이 아닙니다"),                # ②훈련
    _msg("민방위", "위급재난", "공습경보가 해제되었습니다"),                                          # ②해제
    {"category": "earthquake", "distance_km": 3.0, "at": "2026-09-23T10:05:00+09:00"},               # ④규모를 모르는 지진
    {"category": "weather_warning", "kind": "호우경보"}, {"category": "traffic_control", "kind": "집회"},
])
def test_ordinary_messages_do_not_stop_anything(cause):
    assert _level(cause) is None


def test_the_whole_trip_comes_before_the_day_when_both_arrive():
    event = classify([_quake(4.5), _msg("민방위", "위급재난", "공습경보")], RULES)
    assert event.level == "trip" and event.category == "disaster_msg"
    assert classify([_msg("민방위", "위급재난", "공습경보"), _quake(4.5)], RULES).level == "trip"      # 순서와 상관없다


@pytest.mark.parametrize("cause,shelter", [
    (_quake(5.0), "quake_outdoor"), (_msg("지진", "긴급재난"), "quake_outdoor"), (_msg("지진해일", "긴급재난"), "quake_outdoor"),
    (_msg("민방위", "위급재난", "공습경보"), "civil_defense"), (_msg("폭발", "긴급재난"), "civil_defense"), (_msg("테러", "긴급재난"), "civil_defense"),
    (_msg("화산", "긴급재난", "화산 분화"), "civil_defense"), (_msg("기타", "긴급재난", "전쟁 상황"), "civil_defense"),
    (_msg("화재", "긴급재난"), None), (_msg("산불", "긴급재난"), None), (_msg("붕괴", "긴급재난"), None),     # 대피 장소 목록 없이 공식 안내만
])
def test_which_kind_of_shelter_is_listed(cause, shelter):
    assert classify([cause], RULES).shelter_type == shelter


def test_the_event_keeps_what_was_read_and_nothing_else():
    event = classify([_msg("지진", "긴급재난", "지진이 발생했습니다. 건물 밖 넓은 곳으로 대피하세요.")], RULES)
    evidence = event.evidence()
    assert evidence == {"category": "disaster_msg", "kind": "지진", "label": "지진(긴급재난)", "step": "긴급재난",
                        "at": "2026-09-23T10:07:00+09:00", "text": "지진이 발생했습니다. 건물 밖 넓은 곳으로 대피하세요.", "level": "day"}
    quake = classify([_quake(5.1)], RULES)
    assert quake.label == "규모 5.1 지진" and quake.kind == "지진" and quake.step is None


def test_the_same_event_has_the_same_key_and_a_different_event_a_different_one():
    a, b = classify([_msg("지진", "긴급재난", "본문 A")], RULES), classify([_msg("지진", "긴급재난", "본문 A")], RULES)
    c = classify([_msg("지진", "긴급재난", "본문 B")], RULES)
    assert a.key == b.key != c.key


def test_switching_it_off_stops_nothing():
    off = SafetyRules(**{**RULES.__dict__, "pause_enabled": False})
    assert classify([_quake(7.0), _msg("민방위", "위급재난", "공습경보")], off) is None


def test_the_real_guardrails_load_and_agree_with_these_cases():
    """설정 파일(`travel.safety`)의 값으로도 같은 결과 — 값이 바뀌면 이 시험이 알려 준다."""
    real = SafetyRules.from_guardrails()
    assert real.pause_enabled is True and real.trip_magnitude_min == 6.0
    assert _level(_quake(5.0), rules=real) == "day" and _level(_quake(6.5), rules=real) == "trip"
    assert _level(_msg("민방위", "위급재난", "공습경보"), rules=real) == "trip"
    assert _level(_msg("호우", "긴급재난"), rules=real) is None
