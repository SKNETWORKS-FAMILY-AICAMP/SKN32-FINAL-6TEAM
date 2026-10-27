# -*- coding: utf-8 -*-
"""`[2026-10-27 A 접수·읽기 전수검사 A03]` 읽기 에이전트(`agent_mode: on`)가 실패했을 때 「답 내용 쪽」(모양 · 스키마 · 인용 — `ValueError` ·
`OllamaContentError`)이면 줄 읽기로 한 번 더 읽고, 「모델 쪽」이면 `reading_model_failed` 다(계약 web-intakes.md · 2026-10-16 2회차 합의 ②).
그런데 그 밖의 **예상하지 못한 예외**(코드 결함 — `KeyError` · `TypeError` · `AttributeError` …)도 「답 내용 쪽」으로 분류돼 줄 읽기로 조용히
대체됐다. 예상하지 못한 장애는 숨기지 않고 올린다 — `pipeline.process` 가 `reading_failed`(고객 문장만, 계약 「예상하지 못한 읽기 장애」)로 끝낸다.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.domains.travel_ops.components.intake import pipeline

TEXT = "10:00 경복궁\n점심은 통인시장 근처에서"


class Agent:
    """에이전트 호출은 `boom` 을 던지고, 줄 읽기(`json`)는 정상으로 답하는 모델(시험용)."""

    model = "fake"

    def __init__(self, boom):
        self.boom, self.json_calls = boom, 0

    def structured(self, system, user, schema, *, num_predict=160):
        raise self.boom

    def json(self, system, user):
        self.json_calls += 1
        return {"spans": [{"line": 1, "quote": "통인시장", "role": "place"}]}


@pytest.mark.parametrize("boom", [KeyError("items"), TypeError("NoneType is not iterable"), AttributeError("x")])
def test_an_unexpected_agent_error_is_not_quietly_replaced_by_line_reading(boom):
    chat = Agent(boom)
    with pytest.raises(type(boom)):
        pipeline.read_source(TEXT, chat=chat, agent=chat, agent_mode="on", today=date(2030, 11, 6))
    assert chat.json_calls == 0, "같은 모델로 줄 읽기를 다시 부르지 않는다"


def test_an_answer_side_failure_still_reads_the_lines_instead():
    chat = Agent(ValueError("읽기 에이전트 답의 모양이 다르다"))
    rows = pipeline.read_source(TEXT, chat=chat, agent=chat, agent_mode="on", today=date(2030, 11, 6))
    agent_row = next(r for r in rows if r["field"] == "reading.agent")
    assert agent_row["value"]["outcome"] == "lines_instead" and chat.json_calls == 1


def test_in_shadow_mode_the_agent_failure_does_not_break_the_rule_reading():
    chat = Agent(KeyError("items"))
    rows = pipeline.read_source(TEXT, chat=chat, agent=chat, agent_mode="shadow", today=date(2030, 11, 6))
    agent_row = next(r for r in rows if r["field"] == "reading.agent")
    assert agent_row["value"]["used"] is False and "KeyError" in agent_row["value"]["error"]
