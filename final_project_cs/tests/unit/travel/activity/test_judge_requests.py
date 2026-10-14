"""판정 요청 — 날짜 사실은 코드가 계산한다(모델이 달력 계산을 틀리지 않게)."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.domains.travel_ops.instances.activity.judge import JudgeRequest, Verdict
from app.domains.travel_ops.instances.activity.judge.requests import date_facts


@pytest.mark.parametrize("at, weekday, nth, last", [
    (datetime(2026, 10, 13, 10), "화요일", 2, False),   # 둘째 화요일
    (datetime(2026, 10, 27, 10), "화요일", 4, True),    # 마지막 화요일
    (datetime(2026, 12, 31, 10), "목요일", 5, True),    # 12월 — 달 길이 계산이 해를 넘긴다
    (datetime(2026, 2, 22, 10), "일요일", 4, True),     # 28일짜리 달
])
def test_weekday_facts(at, weekday, nth, last):
    facts = date_facts(at, today=date(2026, 10, 6))
    assert (facts["weekday"], facts["nth_weekday_in_month"], facts["is_last_weekday_in_month"]) == (weekday, nth, last)
    assert facts["is_public_holiday"] is None    # ★모른다 — 지어내지 않는다


def test_aware_time_is_read_in_korea():
    facts = date_facts(datetime(2026, 10, 6, 16, 0, tzinfo=UTC))
    assert facts["date"] == "2026-10-07" and facts["weekday"] == "수요일"


def test_unknown_time_gives_no_date_facts():
    facts = date_facts(None, today=date(2026, 10, 6))
    assert facts["today"] == "2026-10-06"
    assert all(facts[k] is None for k in ("starts_at", "date", "weekday", "nth_weekday_in_month"))


def test_kinds_and_values_are_closed_sets():
    with pytest.raises(ValueError):
        JudgeRequest("nope", {})
    with pytest.raises(ValueError):
        Verdict("closure", "open", "llm")      # closure 에는 open 이 없다


def test_closure_request_carries_holiday_facts():
    """★성립 판정이 물어 온 공휴일 사실이 요청에 실린다 — 규칙과 LLM 이 같은 사실을 본다(병합 2026-10-06)."""
    from app.domains.travel_ops.instances.activity.judge import JudgeContext, RuleJudge, requests
    from app.domains.travel_ops.instances.activity.judge.llm import payload_for

    at = datetime(2026, 10, 9, 14)                                   # 한글날
    holidays = {"2026-10-09": {"is_holiday": True, "holiday_name": "한글날"}}
    req = requests.closure("매주 토요일~일요일 / 법정공휴일", at, holidays)
    payload = payload_for(req)
    assert payload["is_public_holiday"] is True and payload["known_holidays"] == {"2026-10-09": "한글날"}
    assert "holidays_raw" not in payload
    assert RuleJudge().judge(JudgeContext(), req).value == "closed"
    unknown = requests.closure("매주 토요일~일요일 / 법정공휴일", at)
    assert payload_for(unknown)["is_public_holiday"] is None
    assert RuleJudge().judge(JudgeContext(), unknown).value == "unknown"
