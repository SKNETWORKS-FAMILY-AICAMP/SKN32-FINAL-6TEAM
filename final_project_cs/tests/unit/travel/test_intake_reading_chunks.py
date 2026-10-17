# -*- coding: utf-8 -*-
"""계획 읽기 — 남은 줄 모델 호출을 **줄 묶음으로** 나눈다. `[2026-10-16]` `components/intake/llm_spans.label_lines`

☆왜: 규칙이 못 읽은 줄을 한 번에 보내면 7일치 긴 글이 로컬 9초 · 유료 8초 한도를 넘겨 줄 전부가 남은 줄(고객이 손으로 고침)이 될 수 있었다.
  실측 근거 `wiki/records/reports/2026-10-16_계획읽기_묶음나누기.md`.

★지키려는 것
 ①묶음은 고른 크기이고 묶음 안에서 1부터 번호를 매겨 보낸다 — 답의 번호를 원래 줄로 되돌리고, **그 묶음 밖** 번호는 버린다
   ☆가르친 E4B 는 받은 번호를 무시하고 목록 안 순서로 답했다(실측) — 그래서 시험의 모델도 순서로 답한다
 ②한 묶음이 실패하면 그 묶음의 줄만 남은 줄로 두고 다음 묶음은 그대로 읽는다(실패를 보고에 남긴다)
 ③전체 상한을 넘으면 **남은 묶음은 보내지 않고** 남은 줄로 둔다 — 사유를 보고에 남긴다(묶음 사이마다 따로 센다)
 ④진행 알림은 처음 0/n, 묶음 하나 끝날 때마다 1씩 — 끝난 묶음만 센다(상한으로 안 보낸 묶음은 `skipped`)
 ⑤원문에 글자 그대로 없는 인용은 묶음으로 나눠도 버린다
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake.llm_spans import label_lines, split_chunks
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.infrastructure.ollama_chat import OllamaError

PLACES = ["경복궁", "광장시장", "북촌한옥마을", "남산타워", "망원시장", "서울숲", "석촌호수", "덕수궁", "창덕궁", "익선동 한옥거리"]
LINES = [f"오후엔 {p} 가 보고 싶어" for p in PLACES]


class Pointer:
    """받은 줄마다 장소를 가리키는 모델 — 받은 번호 그대로 답한다(1부터). 받은 메시지를 남긴다. `fail` 에 든 호출 번호(1부터)는 실패한다."""

    def __init__(self, *, fail: tuple[int, ...] = (), extra: list[dict] | None = None) -> None:
        self.users: list[str] = []
        self.fail, self.extra = fail, extra or []

    def json(self, system: str, user: str) -> dict:
        self.users.append(user)
        if len(self.users) in self.fail:
            raise OllamaError("모든 모델 경로가 실패했다: ollama=timeout, openai=timeout")
        spans = []
        for row in user.splitlines():
            number, text = row.split(": ", 1)
            place = next(p for p in PLACES if p in text)
            spans.append({"line": int(number), "quote": place, "role": "place"})
        return {"spans": spans + self.extra}


def numbers(user: str) -> list[int]:
    return [int(row.split(":", 1)[0]) for row in user.splitlines()]


@pytest.mark.parametrize(("count", "size", "widths"), [
    (46, 8, [8, 8, 8, 8, 7, 7]),        # 끝 묶음만 작게 남기지 않는다
    (10, 4, [4, 3, 3]),
    (8, 8, [8]),
    (5, 0, [5]),                         # 0 이면 전처럼 한 번
    (0, 8, []),
])
def test_chunks_are_even_and_keep_every_line_once(count, size, widths):
    unread = list(range(3, 3 + count))
    chunks = split_chunks(unread, size)
    assert [len(c) for c in chunks] == widths
    assert [n for c in chunks for n in c] == unread


def test_each_call_gets_only_its_own_lines_numbered_from_one_and_answers_map_back():
    chat = Pointer()
    lines = ["1일차 10월 20일", *LINES[:5], "2일차 10월 21일", *LINES[5:]]                 # 머리줄(규칙이 읽는다)이 사이에 있어 원래 번호가 띄엄띄엄
    unread = [2, 3, 4, 5, 6, 8, 9, 10, 11, 12]
    _, items, report = label_lines(lines, unread, chat, chunk_lines=4)
    assert [numbers(u) for u in chat.users] == [[1, 2, 3, 4], [1, 2, 3], [1, 2, 3]]          # 묶음마다 1부터
    assert [u.splitlines()[0].split(": ", 1)[1] for u in chat.users] == [LINES[0], LINES[4], LINES[7]]
    assert [item.title.text for item in items] == PLACES                                  # 묶음으로 나눠도 전부 읽는다
    assert [item.line for item in items] == unread                                        # 답의 번호가 원래 줄로 돌아갔다
    assert [c["lines"] for c in report["chunks"]] == [[2, 3, 4, 5], [6, 8, 9], [10, 11, 12]]
    assert report["asked_lines"] == 10 and report["accepted"] == 10 and "error" not in report


def test_a_span_pointing_outside_its_chunk_is_rejected():
    chat = Pointer(extra=[{"line": 11, "quote": "창덕궁", "role": "place"}])             # 어느 묶음에도 없는 11번이 답마다 섞였다
    _, items, report = label_lines(LINES, list(range(1, 11)), chat, chunk_lines=4)
    assert [i.title.text for i in items].count("창덕궁") == 1                              # 창덕궁(9줄)은 자기 묶음에서 한 번만
    assert sum(1 for r in report["rejected"] if r == {"why": "남은 줄이 아니거나 모르는 역할", "line": 11, "role": "place"}) == 3


def test_an_answer_in_original_numbers_still_lands_on_its_line_when_the_quote_is_there():
    """원래 번호로 답하는 모델(옛 계약) — 순서 번호의 줄에 인용이 없고 원래 번호의 줄에 있으면 그 줄로 받는다."""
    lines = ["1일차 10월 20일", "점심은 토속촌에서 먹을래", "저녁엔 광장시장"]

    class Old:
        def json(self, system, user):
            return {"spans": [{"line": 2, "quote": "토속촌", "role": "place"}, {"line": 3, "quote": "광장시장", "role": "place"}]}

    _, items, report = label_lines(lines, [2, 3], Old(), chunk_lines=0)
    assert [(i.line, i.title.text) for i in items] == [(2, "토속촌"), (3, "광장시장")]      # 순서 2번(3줄)에 「토속촌」이 없다 → 원래 2줄
    assert report["accepted"] == 2 and report["rejected"] == []


def test_a_quote_not_in_the_original_is_still_dropped_when_chunked():
    chat = Pointer(extra=[{"line": 2, "quote": "광잔시장", "role": "place"}])
    _, _, report = label_lines(LINES, list(range(1, 11)), chat, chunk_lines=4)
    assert {"why": "원문에 없는 인용", "line": 2, "quote": "광잔시장"} in report["rejected"]


def test_a_failed_chunk_leaves_only_its_lines_unread_and_says_so():
    chat = Pointer(fail=(2,))
    events = []
    _, items, report = label_lines(LINES, list(range(1, 11)), chat, chunk_lines=4, on_chunk=events.append)
    assert [i.title.text for i in items] == PLACES[:4] + PLACES[7:]                       # 5~7줄만 빠진다
    assert report["left_lines"] == [5, 6, 7]
    assert report["chunks"][1]["error"].startswith("OllamaError") and "error" not in report["chunks"][0]
    assert report["error"].startswith("1/3 묶음 실패")                                      # 화면이 읽는 한 줄 — 숨기지 않는다
    assert events[-1] == {"done": 3, "total": 3, "failed": 1, "skipped": 0}


def test_a_single_call_failure_keeps_the_old_error_line():
    chat = Pointer(fail=(1,))
    _, items, report = label_lines(LINES, list(range(1, 11)), chat, chunk_lines=0)
    assert items == [] and report["left_lines"] == list(range(1, 11))
    assert report["error"].startswith("OllamaError: 모든 모델 경로가 실패했다")


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_over_the_total_limit_the_remaining_chunks_are_not_sent():
    clock = Clock()
    chat = Pointer()
    real = chat.json

    def slow(system, user):
        clock.now += 7.0                                                                  # 묶음 하나에 7초
        return real(system, user)

    chat.json = slow
    events = []
    _, items, report = label_lines(LINES, list(range(1, 11)), chat, chunk_lines=4, total_seconds=10, on_chunk=events.append,
                                   clock=clock)
    assert len(chat.users) == 2                                                           # 7초 → 보냄, 14초 → 상한(10초)을 넘어 세 번째는 안 보낸다
    assert [i.title.text for i in items] == PLACES[:7]
    assert report["left_lines"] == [8, 9, 10]
    assert report["chunks"][2] == {"lines": [8, 9, 10], "skipped": "total_seconds"}
    assert report["deadline"] == {"total_seconds": 10, "spent": 14.0, "skipped_chunks": 1}
    assert events == [{"done": 0, "total": 3, "failed": 0, "skipped": 0}, {"done": 1, "total": 3, "failed": 0, "skipped": 0},
                      {"done": 2, "total": 3, "failed": 0, "skipped": 0}, {"done": 2, "total": 3, "failed": 0, "skipped": 1}]


def test_progress_counts_finished_chunks_in_order_and_a_broken_listener_does_not_stop_reading():
    events = []
    label_lines(LINES, list(range(1, 11)), Pointer(), chunk_lines=4, on_chunk=events.append)
    assert [(e["done"], e["total"]) for e in events] == [(0, 3), (1, 3), (2, 3), (3, 3)]

    def boom(_):
        raise RuntimeError("알림 장애")

    _, items, _ = label_lines(LINES, list(range(1, 11)), Pointer(), chunk_lines=4, on_chunk=boom)
    assert len(items) == 10


def test_read_source_passes_the_limits_and_reports_the_chunks():
    text = "\n".join(["1일차 10월 20일", *LINES])
    events = []
    rows = read_source(text, chat=Pointer(), today=date(2026, 10, 16), now=datetime(2026, 10, 16, 9, tzinfo=ZoneInfo("Asia/Seoul")),
                       chunk_lines=4, reading_seconds=0, on_reading=events.append)
    report = next(r["value"] for r in rows if r["field"] == "reading.llm")
    assert report["chunk_lines"] == 4 and len(report["chunks"]) == 3
    titles = [r["value"] for r in rows if r["field"].endswith(".title")]
    assert titles == PLACES
    assert events[-1]["done"] == 3


def test_read_source_reads_the_limits_from_the_guardrails_when_not_given():
    from app.domains.travel_ops.components.intake import pipeline

    assert pipeline._reading_limits(None, None) == (8, 60.0)          # 근거: 실측 보고서 · `config/guardrails.yaml` 주석
    assert pipeline._reading_limits(3, 5) == (3, 5.0)
    assert pipeline._reading_limits(0, None) == (0, 60.0)
