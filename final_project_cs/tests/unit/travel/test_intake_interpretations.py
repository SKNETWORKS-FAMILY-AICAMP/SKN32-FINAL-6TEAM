# -*- coding: utf-8 -*-
"""해석 확인 질문(`intake/interpretations.py`) — 읽기 AI 와 규칙이 같은 줄을 다르게 읽으면 AI 의 읽기를 1안으로 두고 묻는다. `[2026-10-20 사용자 지시]`

☆2026-10-19 오라클 ARM 접수: 읽기 AI 는 「오후 13시~16시 정도 …」를 **빈 시간**으로 읽었는데, 코드가 그 줄을 「AI 가 빠뜨린 줄」로 보고 규칙 일정 「정도」를 넣었고
  장소 찾기의 오타 고침이 「정돈 대학로본점」으로 바꿨다. ★이제 규칙 일정은 **뺀 채로** 남고(1안 = AI 의 읽기), 선택지로 「정돈 대학로본점(오타로 볼 때)」 ·
  「「정도」 이름 그대로 찾기」를 보인다. AI 가 아무것으로도 읽지 않은 시각 줄은 전처럼 규칙 일정을 넣는다.
(시험 글은 실제 접수 원문이 아니라 같은 모양으로 새로 쓴 것이다.)
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.intake import interpretations
from app.domains.travel_ops.components.intake.pipeline import read_source

TODAY = date(2026, 10, 16)
TEXT = "1일차 · 2026-10-22\n11:00 서울역\n오후 1시~4시 정도\n세 시간 비는데 실내로 뭐 하면 좋을까\n17:00 광장시장 저녁"
SOURCE = "s-1"


def _item(quote, start, *, kind="activity"):
    return {"place_quote": quote, "day": 1, "date": "2026-10-22", "date_quote": "1일차 · 2026-10-22", "start": start, "end": None,
            "time_quote": start, "kind": kind}


def _answer(items, *, gaps=(), pieces=()):
    return {"guard": {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None},
            "pieces": list(pieces), "items": list(items), "moves": [], "conditions": [], "preferences": [], "gaps": list(gaps),
            "requests": ["register"], "missing": [], "trip": {"party_size": None, "days": None, "nights": None}}


class Agent:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, answer):
        self.answer = answer

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


OUR_PLACES = [{"place_id": "11111111-1111-1111-1111-111111111111", "name": "정돈 대학로본점", "kind": "dining",
               "latitude": 37.5818, "longitude": 127.0011},
              {"place_id": "22222222-2222-2222-2222-222222222222", "name": "서울역", "kind": "activity",
               "latitude": 37.5547, "longitude": 126.9707},
              {"place_id": "33333333-3333-3333-3333-333333333333", "name": "광장시장", "kind": "activity",
               "latitude": 37.5700, "longitude": 126.9996}]

GAP = {"kind": "free_slot", "day": 1, "start": "13:00", "end": "16:00", "quote": "오후 1시~4시 정도"}


def _read(gaps=(GAP,), pieces=()):
    agent = Agent(_answer([_item("서울역", "11:00"), _item("광장시장", "17:00", kind="dining")], gaps=gaps, pieces=pieces))
    return read_source(TEXT, today=TODAY, agent=agent, agent_mode="on", position=0, our_places=OUR_PLACES)


def _field(rows, name):
    return next((r for r in rows if r["field"] == name), None)


def _claims(rows):
    """읽기 값 줄 → DB 에 적힌 모양(원본 · 만든 순서)."""
    return [{"source_id": SOURCE, "field": r["field"], "value": r.get("value"), "method": r.get("method"),
             "evidence": r.get("evidence") or {}, "needs_review": r.get("needs_review", False), "note": r.get("note")} for r in rows]


def test_a_line_the_agent_read_as_free_time_keeps_the_rule_item_out_and_asks():
    rows = _read()
    assert _field(rows, "items[2].title")["value"] == "정도"                     # 규칙 일정은 남는다(2안에 쓴다)
    removed = _field(rows, "items[2].removed")
    assert removed["value"] is True and removed["method"] == "llm_agent"         # 1안 = AI 의 읽기 — 뺀 채로
    assert removed["evidence"]["reading"]["kind"] == "free_slot"
    question = _field(rows, interpretations.QUESTION_FIELD + "q-0-3")
    assert question is not None and question["value"]["index"] == 2 and question["value"]["line"] == 3
    place = _field(rows, "items[2].place")                                       # 장소는 찾아 둔다 — 오타 고침이어도 지어낸 이름이 아니다
    assert place["value"]["name"] == "정돈 대학로본점" and place["evidence"]["method"] == "typo"


def test_a_timed_line_the_agent_did_not_read_at_all_is_still_filled_from_rules():
    rows = _read(gaps=())
    assert _field(rows, "items[2].title")["value"] == "정도"
    assert _field(rows, "items[2].removed") is None                              # 옛 동작 그대로 — 묻지 않는다
    assert not any(r["field"].startswith(interpretations.QUESTION_FIELD) for r in rows)
    assert "빠뜨린 줄" in _field(rows, "items[2].title")["note"]


def test_a_plan_ask_piece_spanning_two_lines_also_counts():
    rows = _read(gaps=(), pieces=({"kind": "plan_ask", "quote": "오후 1시~4시 정도 세 시간 비는데 실내로 뭐 하면 좋을까"},))
    assert _field(rows, "items[2].removed")["value"] is True
    assert _field(rows, interpretations.QUESTION_FIELD + "q-0-3")["value"]["reading"]["kind"] == "plan_ask"


def test_short_lines_are_not_swallowed_by_a_long_quote():
    out = SimpleNamespace(gaps=[], pieces=[{"kind": "plan_ask", "quote": "숙소 도착하면 근처 추천해줘"}])
    assert interpretations.contested_lines(["숙소", "숙소 도착하면 근처 추천해줘"], out) == {2: {
        "kind": "plan_ask", "quote": "숙소 도착하면 근처 추천해줘", "day": None, "start": None, "end": None}}


def test_the_view_puts_the_agent_reading_first_and_offers_the_rule_item_and_the_literal_name():
    rows = _read()
    [question] = interpretations.view(_claims(rows), {SOURCE: 0})
    assert question["id"] == "q-0-3" and question["item"] == "0-2" and question["quote"] == "오후 1시~4시 정도"
    assert question["applied"] == "reading" and question["answer"] is None
    first, item, literal = question["options"]
    assert (first["id"], first["recommended"]) == ("reading", True)
    assert first["label"] == "13:00~16:00 빈 시간" and "빈 시간으로 둬요" in first["effect"]
    assert "오후 1시~4시 정도" in first["reason"]
    assert item["id"] == "item" and "정돈 대학로본점" in item["label"] and "오타" in item["label"] and not item["recommended"]
    assert (literal["id"], literal["action"], literal["query"]) == ("item_search", "pick_myself", "정도")


def test_answers_are_checked_and_become_only_the_edits_that_change_the_draft():
    rows = _read()
    questions = interpretations.view(_claims(rows), {SOURCE: 0})
    with pytest.raises(interpretations.InvalidAnswers) as bad:
        interpretations.check({"q-9-9": "reading", "q-0-3": "nope"}, questions)
    assert {p["reason"] for p in bad.value.problems} == {"unknown_question", "unknown_option"}
    assert interpretations.edits_for(interpretations.check({"q-0-3": "reading"}, questions), questions) == []      # 1안 = 지금 판 그대로
    assert interpretations.edits_for({"q-0-3": "item_search"}, questions) == [
        {"source_id": SOURCE, "field": "items[2].removed", "value": False}]


def test_after_choosing_the_rule_item_the_view_follows_the_new_draft_and_switching_back_removes_it():
    claims = _claims(_read())
    claims += [{"source_id": SOURCE, "field": "items[2].removed", "value": False, "method": "customer",
                "evidence": {"source": "customer", "via": "interpretation"}, "needs_review": False, "note": None},
               {"source_id": SOURCE, "field": interpretations.ANSWER_FIELD + "q-0-3", "value": "item", "method": "customer",
                "evidence": {"source": "customer"}, "needs_review": False, "note": None}]
    [question] = interpretations.view(claims, {SOURCE: 0})
    assert (question["answer"], question["applied"]) == ("item", "item")
    assert interpretations.edits_for({"q-0-3": "reading"}, [question]) == [
        {"source_id": SOURCE, "field": "items[2].removed", "value": True}]


def test_loading_means_the_customer_still_sees_reading():
    assert interpretations.loading("reading", "reading") and interpretations.loading("review", "checking")
    assert not interpretations.loading("review", "review") and not interpretations.loading("confirmed", "review")


def test_settled_items_are_prepared_too_but_not_lodging_locked_booked_or_unplaced():
    from app.domains.travel_ops.components.intake.prepared import settled_target

    base = {"kind": "dining", "place_state": "found", "place": {"name": "광장시장"}, "rows": []}
    assert settled_target(base)
    assert not settled_target({**base, "locked": True}) and not settled_target({**base, "booked": True})
    assert not settled_target({**base, "removed": True}) and not settled_target({**base, "place": None})
    assert not settled_target({**base, "kind": "lodging"}) and not settled_target({**base, "place_state": "picked_nearest"})
