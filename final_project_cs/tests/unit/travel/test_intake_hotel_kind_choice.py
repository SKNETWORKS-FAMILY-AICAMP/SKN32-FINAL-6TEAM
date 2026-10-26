# -*- coding: utf-8 -*-
"""호텔 줄의 일정 종류(숙박 · 활동 · 식사) 확인 질문과 숙소 후보 고르기. `[2026-10-26 사용자 지시 — 호텔 종류 확인]`

사용자: 「호텔만 입력해도 후보 하나가 자동으로 잡힌다 — 원래는 후보 3개 중 사용자가 고른다」 · 「호텔이 숙박이 아니라 액티비티로 잡힌다 —
호텔에서 하는 활동 · 식사도 있으니 명확히 지정하지 않으면 검증 화면에서 무엇으로 잡을지 고르게 해야 한다」 · 「호텔 체크인을 써야만 숙박이 된다」.

☆전에는 ① 이름 없는 「호텔」 줄을 먼저 채우기가 숙소 추천의 첫 후보로 바로 채웠고(`prefill` → `gaps.settle`) ② 읽기 AI 가 숙박(`lodging`)으로
  읽어도 조립(`assemble._item`)이 활동 · 식사만 받아 활동이 됐으며 ③ 숙박이 되는 길은 줄에 「체크인」 글자가 있을 때(`_stays`)뿐이었고,
  확인 화면 고치기(`pipeline.edit`)도 종류를 활동 · 식사만 받아 고객도 숙박으로 바꿀 수 없었다.
★이제 장소가 숙소인데 원문이 종류를 정하지 않으면 해석 확인 질문(`interpretations`, P6 와 같은 화면 길)으로 숙박 · 활동 · 식사를 묻는다 —
  1안은 읽은 종류(읽기 AI 일 때만 추천 표시), 답하기 전에는 1안으로 계산하되 **등록은 막는다**(`kind_unanswered`). 숙박을 고르면 체크인 줄과 같은
  숙박 항목이 된다(체크인 · 체크아웃은 B안 규칙으로 채우고 「규칙으로 채움」으로 보인다).
(시험 글은 실제 접수 원문이 아니라 같은 모양으로 새로 쓴 것이다.)
"""
from __future__ import annotations

from datetime import date

import pytest

from app.domains.travel_ops.components.intake import interpretations
from app.domains.travel_ops.components.intake.assemble import collect
from app.domains.travel_ops.components.intake.pipeline import IntakeRejected, _checked, read_source

TODAY = date(2026, 10, 16)
SOURCE = "s-1"
HOTEL_ID = "44444444-4444-4444-4444-444444444444"
OUR_PLACES = [{"place_id": HOTEL_ID, "name": "롯데호텔 서울", "kind": "lodging", "content_type_id": "32",
               "latitude": 37.5653, "longitude": 126.9810},
              {"place_id": "22222222-2222-2222-2222-222222222222", "name": "경복궁", "kind": "activity",
               "latitude": 37.5796, "longitude": 126.9770}]


def _item(quote, start, *, kind="activity", day=1, when="2026-10-22"):
    return {"place_quote": quote, "day": day, "date": when, "date_quote": None, "start": start, "end": None,
            "time_quote": start, "kind": kind}


def _answer(items):
    return {"guard": {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None},
            "pieces": [], "items": list(items), "moves": [], "conditions": [], "preferences": [], "gaps": [],
            "requests": ["register"], "missing": [], "trip": {"party_size": None, "days": None, "nights": None}}


class Agent:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, answer):
        self.answer = answer

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


def _read(text, items):
    return read_source(text, today=TODAY, agent=Agent(_answer(items)), agent_mode="on", position=0, our_places=OUR_PLACES)


def _claims(rows):
    return [{"source_id": SOURCE, "field": r["field"], "value": r.get("value"), "method": r.get("method"),
             "evidence": r.get("evidence") or {}, "needs_review": r.get("needs_review", False), "note": r.get("note")} for r in rows]


def _sources(text):
    return [{"source_id": SOURCE, "position": 0, "kind": "text", "transcript": text}]


def _kind_questions(rows):
    return [q for q in interpretations.view(_claims(rows), {SOURCE: 0}) if q.get("type") == "kind"]


TEXT = "2026-10-22\n10:00 경복궁\n15:00 롯데호텔 서울"


def test_a_named_hotel_without_kind_words_asks_stay_activity_or_meal_with_the_ai_reading_first():
    rows = _read(TEXT, [_item("경복궁", "10:00"), _item("롯데호텔 서울", "15:00")])
    [question] = _kind_questions(rows)
    assert question["kind"] == "interpretation", "화면(asksOf)이 그리는 해석 확인 질문과 같은 모양"
    assert question["item"] == "0-1" and question["answer"] is None and question["applied"] == "reading"
    assert "롯데호텔 서울" in question["question"]
    first, *others = question["options"]
    assert (first["id"], first["label"], first["recommended"]) == ("reading", "활동", True)
    assert sorted(o["id"] for o in others) == ["dining", "lodging"]
    assert {o["label"] for o in others} == {"숙박", "식사"} and not any(o["recommended"] for o in others)


def test_the_sight_line_gets_no_kind_question():
    rows = _read(TEXT, [_item("경복궁", "10:00"), _item("롯데호텔 서울", "15:00")])
    assert [q["item"] for q in _kind_questions(rows)] == ["0-1"]


@pytest.mark.parametrize("line, quote, kind", [("15:00 롯데호텔 서울 체크인", "롯데호텔 서울 체크인", "lodging"),
                                                ("08:00 롯데호텔 서울 조식", "롯데호텔 서울 조식", "dining")])
def test_a_hotel_line_whose_words_say_the_kind_is_not_asked(line, quote, kind):
    text = f"2026-10-22\n{line}"
    rows = _read(text, [_item(quote, line[:5], kind=kind)])
    assert _kind_questions(rows) == []


def test_a_hotel_the_ai_read_as_a_stay_is_a_stay_without_check_in_words_but_cannot_register_unanswered():
    text = "2026-10-22\n10:00 경복궁\n2026-10-23\n09:00 경복궁\n2026-10-22\n롯데호텔 서울"
    rows = _read(text, [_item("경복궁", "10:00"), _item("경복궁", "09:00", day=2, when="2026-10-23"),
                        _item("롯데호텔 서울", None, kind="lodging")])
    kind_rows = [r for r in rows if r["field"] == "items[2].kind"]
    assert [(r["value"], r["method"]) for r in kind_rows] == [("lodging", "llm_agent")], "AI 의 숙박 읽기를 버리지 않는다"
    [question] = _kind_questions(rows)
    first = question["options"][0]
    assert (first["id"], first["label"], first["recommended"]) == ("reading", "숙박", True)
    got = collect(sources=_sources(text), claims=_claims(rows))
    stay = next(r for r in got.rows if r["index"] == 2)
    assert (stay["kind"], stay["date"], stay["start"], stay["end_date"], stay["end"]) == ("lodging", "2026-10-22", "15:00", "2026-10-23", "11:00")
    notes = {f["field"]: f["note"] for f in got.filled}
    assert "체크인 시각이 없어 15:00" in notes["items[2].starts_at"] and "체크아웃 줄이 없어" in notes["items[2].ends_at"]
    assert [(p.code, p.field) for p in got.problems if p.code == "kind_unanswered"] == [("kind_unanswered", "items[2].kind")]


def test_answering_the_reading_lifts_the_block_without_changing_the_draft():
    rows = _read(TEXT, [_item("경복궁", "10:00"), _item("롯데호텔 서울", "15:00")])
    questions = _kind_questions(rows)
    picked = interpretations.check({questions[0]["id"]: "reading"}, questions)
    assert interpretations.edits_for(picked, questions) == []
    claims = _claims(rows) + [{"source_id": SOURCE, "field": interpretations.ANSWER_FIELD + questions[0]["id"], "value": "reading",
                               "method": "customer", "evidence": {"source": "customer"}, "needs_review": False, "note": None}]
    got = collect(sources=_sources(TEXT), claims=claims)
    assert not any(p.code == "kind_unanswered" for p in got.problems)
    [after] = _kind_questions([{**c} for c in claims])
    assert after["answer"] == "reading", "답한 질문은 다시 그려지지 않는다(answer 가 있다)"


def test_choosing_stay_becomes_a_kind_edit_and_the_draft_turns_into_a_stay_then_back():
    rows = _read(TEXT, [_item("경복궁", "10:00"), _item("롯데호텔 서울", "15:00")])
    questions = _kind_questions(rows)
    qid = questions[0]["id"]
    assert interpretations.edits_for({qid: "lodging"}, questions) == [
        {"source_id": SOURCE, "field": "items[1].kind", "value": "lodging"}]
    assert interpretations.edits_for({qid: "dining"}, questions) == [
        {"source_id": SOURCE, "field": "items[1].kind", "value": "dining"}]
    stay_claims = _claims(rows) + [
        {"source_id": SOURCE, "field": "items[1].kind", "value": "lodging", "method": "customer",
         "evidence": {"source": "customer", "via": "interpretation"}, "needs_review": False, "note": None},
        {"source_id": SOURCE, "field": interpretations.ANSWER_FIELD + qid, "value": "lodging", "method": "customer",
         "evidence": {"source": "customer"}, "needs_review": False, "note": None}]
    got = collect(sources=_sources(TEXT), claims=stay_claims)
    stay = next(r for r in got.rows if r["index"] == 1)
    assert (stay["kind"], stay["end_date"], stay["end"]) == ("lodging", "2026-10-23", "11:00")
    assert not any(p.code == "kind_unanswered" for p in got.problems)
    [after] = [q for q in interpretations.view(stay_claims, {SOURCE: 0}) if q.get("type") == "kind"]
    assert (after["answer"], after["applied"]) == ("lodging", "lodging")
    # 다시 활동으로 — 숙박 기간(끝 날) 같은 파생 값이 남지 않는다
    back = stay_claims + [{"source_id": SOURCE, "field": "items[1].kind", "value": "activity", "method": "customer",
                           "evidence": {"source": "customer", "via": "interpretation"}, "needs_review": False, "note": None}]
    row = next(r for r in collect(sources=_sources(TEXT), claims=back).rows if r["index"] == 1)
    assert (row["kind"], row["end_date"]) == ("activity", None)


def test_a_kind_the_customer_set_on_the_edit_screen_counts_as_the_answer():
    rows = _read(TEXT, [_item("경복궁", "10:00"), _item("롯데호텔 서울", "15:00")])
    claims = _claims(rows) + [{"source_id": SOURCE, "field": "items[1].kind", "value": "dining", "method": "customer",
                               "evidence": {"source": "customer"}, "needs_review": False, "note": None}]
    assert not any(p.code == "kind_unanswered" for p in collect(sources=_sources(TEXT), claims=claims).problems)
    [question] = [q for q in interpretations.view(claims, {SOURCE: 0}) if q.get("type") == "kind"]
    assert question["answer"] == "dining" and question["applied"] == "dining"


def test_a_removed_hotel_line_does_not_block_registration():
    rows = _read(TEXT, [_item("경복궁", "10:00"), _item("롯데호텔 서울", "15:00")])
    claims = _claims(rows) + [{"source_id": SOURCE, "field": "items[1].removed", "value": True, "method": "customer",
                               "evidence": {"source": "customer"}, "needs_review": False, "note": None}]
    assert not any(p.code == "kind_unanswered" for p in collect(sources=_sources(TEXT), claims=claims).problems)


def test_the_review_edit_accepts_stay_as_a_kind_but_nothing_else_new():
    value, _evidence, _extra = _checked("items[1].kind", "lodging")
    assert value == "lodging"
    with pytest.raises(IntakeRejected):
        _checked("items[1].kind", "flight")


# ── 이름 없는 「호텔」 줄: 먼저 채우기가 후보 하나로 확정하지 않는다 ─────────────────────────────
def _prefill_with_one_hotel_candidate(monkeypatch, candidates):
    from copy import deepcopy

    from app.domains.travel_ops.components.intake import autofix, pipeline, prefill

    initial = {"items": [{"id": "0-0", "index": 0, "source_id": "s", "title": "호텔", "kind": "activity", "date": "2030-11-06",
                          "place_state": "needs_choice", "place": None, "starts_at": "20:00", "ends_at": None,
                          "parts": {"label": "숙소", "content_type": "32"}}], "moves": []}
    views, edits_seen = {1: initial}, []

    def plan(_conn, *, review, **kwargs):
        return {"changes": [{"id": "0-0", "source_id": "s", "index": 0, "title": "호텔", "from": {"place": None},
                             "to": {"place": {"name": name}}, "edits": [{"field": "place", "value": {"name": name}}],
                             "hours_known": False} for name in candidates[:1]], "kept": []}

    def edit(_conn, *, revision, edits, **kwargs):
        edits_seen.extend(edits)
        views[revision + 1] = deepcopy(views[revision])
        return revision + 1

    monkeypatch.setattr(pipeline, "current_review", lambda conn, **kw: (None, views[kw["revision"]]))
    monkeypatch.setattr(pipeline, "_claims", lambda *args: [])
    monkeypatch.setattr(pipeline, "_trip_fields", lambda claims: {})
    monkeypatch.setattr(pipeline, "edit", edit)
    monkeypatch.setattr(autofix, "plan", plan)
    monkeypatch.setattr(prefill, "_store", lambda conn, **kw: None)
    monkeypatch.setattr(prefill.lodging_context, "generic", lambda item: True)
    monkeypatch.setattr(prefill.lodging_context, "protected", lambda item: False)
    result = prefill.run(None, tenant_id="test", customer_id=None, intake_id=None, revision=1, plan_slot=lambda gap, draft: [])
    return result, edits_seen


@pytest.mark.parametrize("candidates", [["단 하나의 호텔"], ["A 호텔", "B 호텔", "C 호텔"], []])
def test_a_nameless_hotel_is_never_filled_by_the_first_candidate_but_asked(monkeypatch, candidates):
    result, edits_seen = _prefill_with_one_hotel_candidate(monkeypatch, candidates)
    assert edits_seen == [] and result["revision"] == 1, "후보가 하나여도 판에 바로 넣지 않는다"
    assert result["filled"] == []
    [asked] = [q for q in result["questions"] if q["kind"] == "lodging_place"]
    assert "후보에서 골라" in asked["question"] and asked["item"] == "0-0"
    assert asked["actions"] == ["pick_candidate", "pick_myself", "no_place"]


def test_the_nameless_hotel_gap_is_the_customers_to_answer():
    from app.domains.travel_ops.components.intake import gaps

    assert gaps.ROUTES["lodging_place"] == "ask_customer"


# ── 후보 목록을 질문에 같이 싣는다 `[2026-10-26 12:52 사용자 보고 — 후보 3개 목록이 바로 안 나온다]` ──────────────
def _cand(name, source="places", rank=1):
    return {"rank": rank, "place": {"name": name, "latitude": 37.56, "longitude": 126.98, "source": source, "kind": "activity",
                                    "content_type_id": "32"}, "basis": "lodging", "reason": "숙소 후보예요", "fits": True, "status": "ok"}


@pytest.mark.parametrize("pool, names", [
    ([_cand("A 호텔"), _cand("B 호텔", rank=2), _cand("C 호텔", rank=3), _cand("D 호텔", rank=4)], ["A 호텔", "B 호텔", "C 호텔"]),
    ([_cand("단 하나의 호텔")], ["단 하나의 호텔"]),
    ([], []),
    ([_cand("지도 호텔", source="kakao"), _cand("목록 호텔", rank=2)], ["목록 호텔"]),
])
def test_the_hotel_question_carries_up_to_three_candidates_and_never_stores_map_values(monkeypatch, pool, names):
    from app.domains.travel_ops.components.intake import candidates as candidates_module

    asked = []

    def alternatives(conn, *, tenant_id, review, item, kakao=None, chat=None, **kwargs):
        asked.append((item["id"], kakao, chat))
        return {"candidates": pool, "notes": []}

    monkeypatch.setattr(candidates_module, "alternatives", alternatives)
    result, edits_seen = _prefill_with_one_hotel_candidate(monkeypatch, ["안 쓰는 첫 후보"])
    assert edits_seen == [] and result["revision"] == 1, "후보를 실어도 판에 넣지 않는다"
    [question] = [q for q in result["questions"] if q["kind"] == "lodging_place"]
    assert [c["place"]["name"] for c in question["candidates"]] == names
    assert asked == [("0-0", None, None)], "카카오 값(약관상 저장 금지)과 모델 이유 문장 없이 한 번만 계산한다"


def test_a_stay_whose_place_is_picked_from_candidates_is_registered_as_a_stay():
    """`[2026-10-26 13:14 사용자 보고 — 등록 뒤 액티비티]` 숙소 후보를 고른 값(장소 값의 kind 는 activity · 분류 32)은 일정 종류를 바꾸지 않는다 — 등록 몸통도 숙박."""
    from app.domains.travel_ops.components.intake.assemble import assemble

    text = "2026-10-22\n10:00 경복궁\n2026-10-23\n09:00 경복궁\n2026-10-22\n호텔"
    rows = _read(text, [_item("경복궁", "10:00"), _item("경복궁", "09:00", day=2, when="2026-10-23"), _item("호텔", None, kind="lodging")])
    claims = _claims(rows) + [
        {"source_id": SOURCE, "field": "items[2].place", "method": "customer", "needs_review": False, "note": None,
         "evidence": {"source": "customer", "picked_from": "tour_api"},
         "value": {"name": "소테츠 프레사 인 서울 명동", "latitude": 37.5636, "longitude": 126.9845, "kind": "activity",
                   "source": "customer_pick", "origin": "tour_api"}},
        {"source_id": SOURCE, "field": interpretations.ANSWER_FIELD + "k-0-2", "value": "reading", "method": "customer",
         "evidence": {"source": "customer"}, "needs_review": False, "note": None}]
    built = assemble(intake_id="i1", revision=3, sources=_sources(text), claims=claims)
    stay = next(i for i in built.body["items"] if i["title"] in ("호텔", "소테츠 프레사 인 서울 명동"))
    assert stay["kind"] == "lodging", stay
    assert stay["ends_at"].startswith("2026-10-23T11:00"), stay
    assert not any(p.code == "kind_unanswered" for p in built.problems)
