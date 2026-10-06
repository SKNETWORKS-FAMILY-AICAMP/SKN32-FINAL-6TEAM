"""RuleJudge — 지금 규칙 판정을 **그대로** 옮기는가(섀도 모드의 비교 기준이 「지금 동작」이어야 한다)."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.modules.travel_ops.activity.feasibility import FeasibilityMixin
from app.modules.travel_ops.activity.judge import JudgeContext, RuleJudge, requests

CTX = JudgeContext()
MONDAY = datetime(2026, 10, 12, 10, 0)
TUESDAY = datetime(2026, 10, 13, 10, 0)


@pytest.mark.parametrize("text, at, expected", [
    ("매주 월요일 휴무", MONDAY, "closed"),
    ("매주 월요일 휴무", TUESDAY, "not_closed"),
    # ★`[2026-10-06]` fix/activity-closure-rule 병합 뒤 규칙이 「매월 둘째 주」를 읽는다(전에는 not_closed)
    ("매월 둘째 주 화요일 휴무", TUESDAY, "closed"),
    ("공휴일 다음날 휴무", TUESDAY, "unknown"),            # 공휴일 사실이 없으면 모름 — 「아님」으로 확정하지 않는다
    (None, MONDAY, "unknown"),
    ("매주 월요일 휴무", None, "unknown"),
])
def test_closure_matches_current_rule(text, at, expected):
    verdict = RuleJudge().judge(CTX, requests.closure(text, at))
    assert verdict.value == expected and verdict.source == "rule"
    current = FeasibilityMixin._weekday_closure_match(text, at)
    assert verdict.value == {True: "closed", False: "not_closed"}.get(current, "unknown")


@pytest.mark.parametrize("request_", [
    requests.operating_hours("09:00~18:00", MONDAY),
    requests.live_status("경복궁", "activity", None, MONDAY),
])
def test_rule_does_not_interpret_hours_or_live_status(request_):
    """지금 코드는 운영시간 원문을 판정에 넣지 않고, 실시간 운영 상태 판정은 없다."""
    verdict = RuleJudge().judge(CTX, request_)
    assert verdict.value == "unknown" and verdict.basis == "rule_does_not_interpret"


@pytest.mark.parametrize("title, code, expected, basis", [
    ("올림픽공원", None, "outdoor", "title"),
    ("국립중앙박물관 전시관", None, "indoor", "title"),
    ("경복궁", "HS01", "outdoor", "category"),
    ("어떤 장소", "SH01", "indoor", "category"),
    ("어떤 장소", None, "unknown", None),
])
def test_weather_sensitive_title_then_category(title, code, expected, basis):
    verdict = RuleJudge().judge(CTX, requests.weather_sensitive(title, code))
    assert (verdict.value, verdict.basis) == (expected, basis)


@pytest.mark.parametrize("messages, expected", [
    ([{"step": "위급재난", "kind": "지진", "text": "x"}], "blocks"),
    ([{"step": "안전안내", "kind": "호우", "text": "x"}], "no_effect"),
    ([], "no_effect"),
])
def test_disaster_by_step_only(messages, expected):
    verdict = RuleJudge().judge(CTX, requests.disaster_effect("경복궁", "activity", messages, MONDAY))
    assert verdict.value == expected
