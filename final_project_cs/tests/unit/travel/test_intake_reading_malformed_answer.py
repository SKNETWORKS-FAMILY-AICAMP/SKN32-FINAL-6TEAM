# -*- coding: utf-8 -*-
"""`[2026-10-27 A 접수·읽기 전수검사]` 남은 줄 모델(`llm_spans.label_lines`)이 답은 했지만 **모양이 다른 답**(`{}` · `{"spans": null}` ·
`{"spans": "…"}` · 배열)을 내면 예전에는 「읽을 것이 없음」(받은 조각 0)으로 성공 처리돼 남은 줄이 조용히 「못 읽은 줄」로 남았다
(계약 web-intakes.md progress{reading}: 끝내 못 읽으면 `reading_model_failed`). 정상인 빈 답 `{"spans": []}` 은 그대로 성공이다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.intake.llm_spans import ReadingFailed, label_lines

LINES = ["10:00 경복궁", "점심은 통인시장 근처에서", "오후 늦게 남산타워"]
UNREAD = [2, 3]


class Answers:
    """모양만 다른 답을 내는 모델(시험용) — 호출은 성공한다."""

    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def json(self, system, user):
        self.calls += 1
        return self.answer


@pytest.mark.parametrize("answer", [{}, {"spans": None}, {"spans": "경복궁"}, ["경복궁"], None, {"items": []}])
def test_a_malformed_answer_is_a_reading_failure_not_an_empty_reading(answer):
    with pytest.raises(ReadingFailed, match="모양"):
        label_lines(LINES, UNREAD, Answers(answer))


def test_an_empty_span_list_is_still_a_valid_answer():
    claims, items, report = label_lines(LINES, UNREAD, Answers({"spans": []}))
    assert (claims, items, report["accepted"], report["spans"]) == ([], [], 0, 0)


def test_read_source_turns_a_malformed_answer_into_the_customer_reading_failure():
    from datetime import date

    with pytest.raises(pipeline.IntakeRejected) as caught:
        pipeline.read_source("\n".join(LINES), chat=Answers({"spans": None}), today=date(2030, 11, 6))
    assert caught.value.code == "reading_model_failed"
