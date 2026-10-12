"""RuleJudge — 활동 팀의 지금 규칙을 **그대로** 옮기는가(평가의 규칙 쪽이 「지금 동작」을 재야 한다).

★`[2026-10-12]` 10-11~12 팀 변경(§8 분류표 · D2-1 · 운영시간 규칙 판정)을 따라가게 다시 맞췄다 — `judge/rule.py` 머리.

★`[2026-10-09]` 비교 기준을 develop 판 규칙으로 바꿨다(D-CS-015): ③ 실내외는 관광공사 분류(`weather_from_class`),
  ④ 재난문자는 공유 점검의 유형 목록 · 심각 낱말 + 재난 정지(`safety.classify`). 전에는 장소명 짐작 · 「위급재난이면 막음」이었다.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.domains.travel_ops.instances.activity.closure_rules import read_closure
from app.domains.travel_ops.instances.activity.judge import JudgeContext, RuleJudge, requests

CTX = JudgeContext()
MONDAY = datetime(2026, 10, 12, 10, 0)
TUESDAY = datetime(2026, 10, 13, 10, 0)


@pytest.mark.parametrize("text, at, expected", [
    ("매주 월요일 휴무", MONDAY, "closed"),
    ("매주 월요일 휴무", TUESDAY, "not_closed"),
    ("매월 둘째 주 화요일 휴무", TUESDAY, "closed"),
    ("공휴일 다음날 휴무", TUESDAY, "unknown"),            # 공휴일 사실이 없으면 모름 — 「아님」으로 확정하지 않는다
    (None, MONDAY, "unknown"),
    ("매주 월요일 휴무", None, "unknown"),
])
def test_closure_matches_the_develop_rule(text, at, expected):
    verdict = RuleJudge().judge(CTX, requests.closure(text, at))
    assert verdict.value == expected and verdict.source == "rule"
    current = read_closure(text, at, None).value
    assert verdict.value == {True: "closed", False: "not_closed"}.get(current, "unknown")


HOURS_DAY = datetime(2026, 10, 14, 0, 0)       # 수요일


@pytest.mark.parametrize("text, hour, minute, expected", [
    ("09:00~18:00", 14, 0, "within"),
    ("09:00~18:00", 19, 30, "outside"),
    ("09:00~18:00(입장마감 17:00)", 17, 30, "outside"),          # 입장 마감 뒤
    ("하절기 09:00~19:00, 동절기 09:00~18:00", 14, 0, "unknown"),  # 규칙으로 못 편다 — sLLM 이 미리 펴 둘 몫
])
def test_operating_hours_follow_the_team_rule(text, hour, minute, expected):
    """`[2026-10-12]` 팀 · 원장과 같은 함수(`read_by_rule` → `hours_verdict`)로 판정한다. 전에는 늘 「모름」이었다."""
    verdict = RuleJudge().judge(CTX, requests.operating_hours(text, HOURS_DAY.replace(hour=hour, minute=minute)))
    assert verdict.value == expected and verdict.source == "rule"


def test_rule_does_not_interpret_live_status():
    verdict = RuleJudge().judge(CTX, requests.live_status("경복궁", "activity", None, MONDAY))
    assert verdict.value == "unknown" and verdict.basis == "rule_does_not_interpret"


@pytest.mark.parametrize("title, code, expected, basis", [
    ("경복궁", "HS01", "unknown", None),                         # ★역사유적은 분류표에 없다 — 장소명으로 짐작하지 않는다
    ("북한산", "NA01", "outdoor", "tour_class"),                  # 대분류 NA(자연) — 중분류 앞 두 글자
    ("한강 수상스키장", "LS03", "outdoor", "tour_class"),
    ("어떤 매장", "SH01", "indoor", "tour_class"),
    ("국립중앙박물관", "EX02", "indoor", "tour_class"),
    ("올림픽공원", None, "outdoor", "tour_class_from_catalog"),   # ★`[2026-10-12]` 코드가 없으면 장소 목록의 분류(VE03 도시공원)
    ("국립중앙박물관", None, "indoor", "tour_class_from_catalog"),  # 목록의 VE07(전시시설)
    ("없는장소이름XYZ", None, "unknown", None),                  # 목록에도 없으면 모름
])
def test_weather_sensitive_uses_the_tour_class(title, code, expected, basis):
    verdict = RuleJudge().judge(CTX, requests.weather_sensitive(title, code))
    assert (verdict.value, verdict.basis) == (expected, basis)


def _msg(step, kind, text="본문", regions=("서울특별시 종로구",)):
    return {"step": step, "kind": kind, "text": text, "regions": list(regions),
            "created_at": "2026-10-12T09:00:00+09:00"}


@pytest.mark.parametrize("messages, sensitive, expected", [
    ([_msg("안전안내", "교통통제")], None, "blocks"),                        # 지역 위험형 — 실내외와 상관없다
    ([_msg("안전안내", "호우")], False, "blocks"),                           # 호우도 지역 위험형(§8) — 실내도 막는다
    ([_msg("긴급재난", "기타", "공습경보 발령")], False, "blocks"),           # 재난 정지 기준(심각 낱말)이 먼저
    ([_msg("안전안내", "폭염")], True, "blocks"),                            # 야외 위험형 — 실외만
    ([_msg("안전안내", "폭염")], False, "no_effect"),
    ([_msg("안전안내", "폭염")], None, "unknown"),                           # 경복궁(HS01)은 분류로 실내외를 못 정한다 — 묻는다
    ([_msg("안전안내", "교통통제", "교통통제 해제")], None, "no_effect"),      # 해제 문자
    ([_msg("안전안내", "정전", "정전 복구가 완료되었습니다")], None, "no_effect"),  # ① 복구 문자(D2-1)
    ([_msg("안전안내", "기타", "세종대로 집회로 혼잡 예상")], None, "no_effect"),  # 반영 안 함(기타)
    ([_msg("안전안내", "기타", "경복궁 관람 전면 중단")], None, "blocks"),     # ③ 장소를 지목한 중단 공지(D2-1)
    ([_msg("안전안내", "교통통제", regions=("부산광역시 해운대구",))], None, "no_effect"),  # 다른 지역 — 닿지 않는다
    ([_msg("안전안내", "교통통제", regions=("서울특별시",))], None, "blocks"),             # 시 전체는 닿는다
    ([], None, "no_effect"),
])
def test_disaster_follows_the_impact_table_for_the_place_district(messages, sensitive, expected):
    """`[2026-10-12]` 팀과 같은 기준 — 재난 정지 → 장소의 구로 거른 문자 → 수정본 §8 분류표 + D2-1 세 규칙."""
    verdict = RuleJudge().judge(CTX, requests.disaster_effect("경복궁", "activity", messages, MONDAY, sensitive))
    assert verdict.value == expected


def test_disaster_is_unknown_when_the_place_district_is_unknown():
    """장소를 목록에서 못 찾으면 구 단위 문자가 닿는지 모른다 — 「영향 없음」으로 정하지 않는다."""
    verdict = RuleJudge().judge(CTX, requests.disaster_effect("없는장소이름XYZ", "activity",
                                                             [_msg("안전안내", "교통통제")], MONDAY, None))
    assert (verdict.value, verdict.basis) == ("unknown", "district_unknown")


def test_the_indoor_outdoor_hint_is_not_sent_to_the_model():
    from app.domains.travel_ops.instances.activity.judge.llm import payload_for

    payload = payload_for(requests.disaster_effect("경복궁", "activity", [_msg("안전안내", "호우")], MONDAY, True))
    assert "weather_sensitive_raw" not in payload
