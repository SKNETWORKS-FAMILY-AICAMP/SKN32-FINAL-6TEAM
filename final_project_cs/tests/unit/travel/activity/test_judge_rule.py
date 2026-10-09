"""RuleJudge — develop 판 활동 팀의 지금 규칙을 **그대로** 옮기는가(평가의 규칙 쪽이 「지금 동작」을 재야 한다).

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


@pytest.mark.parametrize("request_", [
    requests.operating_hours("09:00~18:00", MONDAY),
    requests.live_status("경복궁", "activity", None, MONDAY),
])
def test_rule_does_not_interpret_hours_or_live_status(request_):
    """develop 판은 요청 때 운영시간 원문을 다시 해석하지 않고(새벽 작업이 요일표로 둔다), 웹 공지는 보지 않는다."""
    verdict = RuleJudge().judge(CTX, request_)
    assert verdict.value == "unknown" and verdict.basis == "rule_does_not_interpret"


@pytest.mark.parametrize("title, code, expected", [
    ("경복궁", "HS01", "unknown"),            # ★역사유적은 develop 분류표에 없다 — 장소명으로 짐작하지 않는다
    ("북한산", "NA01", "outdoor"),            # 대분류 NA(자연) — 중분류 앞 두 글자
    ("한강 수상스키장", "LS03", "outdoor"),
    ("어떤 매장", "SH01", "indoor"),
    ("국립중앙박물관", "EX02", "indoor"),
    ("올림픽공원", None, "unknown"),          # ★전에는 장소명으로 outdoor 였다
])
def test_weather_sensitive_uses_the_tour_class_only(title, code, expected):
    verdict = RuleJudge().judge(CTX, requests.weather_sensitive(title, code))
    assert verdict.value == expected
    assert verdict.basis == ("tour_class" if expected != "unknown" else None)


def _msg(step, kind, text="본문"):
    return {"step": step, "kind": kind, "text": text, "regions": ["서울특별시 종로구"],
            "created_at": "2026-10-12T09:00:00+09:00"}


@pytest.mark.parametrize("messages, sensitive, expected", [
    ([_msg("안전안내", "교통통제")], None, "blocks"),                       # 장소형 유형 — 실내외와 상관없다
    ([_msg("긴급재난", "기타", "공습경보 발령")], False, "blocks"),          # 심각 낱말
    ([_msg("안전안내", "호우")], True, "blocks"),                          # 날씨형 — 실외만
    ([_msg("안전안내", "호우")], False, "no_effect"),
    ([_msg("안전안내", "호우")], None, "unknown"),                         # 실내외를 모르면 단정하지 않는다
    ([_msg("안전안내", "교통통제", "교통통제 해제")], None, "no_effect"),     # 해제 문자
    ([_msg("안전안내", "기타", "세종대로 집회로 혼잡 예상")], None, "no_effect"),
    ([], None, "no_effect"),
])
def test_disaster_follows_the_shared_check_and_safety_stop(messages, sensitive, expected):
    verdict = RuleJudge().judge(CTX, requests.disaster_effect("경복궁", "activity", messages, MONDAY, sensitive))
    assert verdict.value == expected


def test_the_indoor_outdoor_hint_is_not_sent_to_the_model():
    from app.domains.travel_ops.instances.activity.judge.llm import payload_for

    payload = payload_for(requests.disaster_effect("경복궁", "activity", [_msg("안전안내", "호우")], MONDAY, True))
    assert "weather_sensitive_raw" not in payload
