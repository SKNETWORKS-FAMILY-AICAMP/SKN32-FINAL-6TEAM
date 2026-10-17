# -*- coding: utf-8 -*-
"""대체 식당 — 규칙 상위 3곳 중 하나를 모델이 고른다(`meal_pick`). 모델은 가짜다 — 부르는 조건 · 답 확인 · 실패 시 규칙 1등을 본다."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.planning.meal_pick import (MealContext, check, make_picker, prompt,
                                                                   should_ask)
from app.domains.travel_ops.components.planning.replan import Candidate

KST = ZoneInfo("Asia/Seoul")
NOON = datetime(2026, 10, 21, 12, 0, tzinfo=KST)


def _cand(key: str, name: str, style: str, *, kind: str = "한식", likeness: int = 2, walk: int = 3,
          added: int = 0) -> Candidate:
    place = {"place_id": key, "name": name, "kind": "dining", "latitude": 37.57, "longitude": 126.98,
             "attributes": {"cuisine": [kind], "category": kind, "style": style}}
    return Candidate(key=key, place=place, changed_items=1, extra_cost_krw=None, shift_minutes=0, walk_min=walk,
                     starts_at=NOON, likeness=likeness, added_move_min=added)


def _three(added_second: int = 0):
    return (_cand("a", "연탄불고기", "고기구이", likeness=2),
            [_cand("b", "산채비빔밥", "한상차림", likeness=3, walk=4, added=added_second),
             _cand("c", "모퉁이커피", "커피·차", kind="카페디저트", likeness=5, walk=2)])


def _ctx(preference: str = "") -> MealContext:
    return MealContext(meal_title="점심", starts_at=NOON,
                       original={"name": "한우마당", "attributes": {"category": "한식", "style": "고기구이"}},
                       preference=preference)


class FakeChat:
    def __init__(self, answer=None, error: Exception | None = None):
        self.answer, self.error, self.calls = answer, error, []

    def structured(self, system, user, schema, *, num_predict=160):
        self.calls.append((system, user, schema))
        if self.error:
            raise self.error
        return self.answer


GOOD = {"pick": "2", "reason": "채식 위주라 비빔밥집을 골랐어요.",
        "cited": [{"candidate": "2", "field": "style", "value": "한상차림"}]}


def test_without_a_preference_the_model_is_not_called():
    best, alternates = _three()
    chat = FakeChat(GOOD)
    pick = make_picker(chat)(best, alternates, _ctx())
    assert pick.by == "rule" and pick.best is best and chat.calls == []


def test_a_valid_pick_swaps_best_and_keeps_the_rule_first_as_an_alternate():
    best, alternates = _three()
    chat = FakeChat(GOOD)
    pick = make_picker(chat)(best, alternates, _ctx("고기는 빼 주세요"))
    assert pick.by == "llm" and pick.best.key == "b"
    assert [c.key for c in pick.alternates] == ["a", "c"]
    assert pick.record()["reason"].startswith("채식")
    assert '"customer_preference": "고기는 빼 주세요"' in chat.calls[0][1]


@pytest.mark.parametrize("answer, why", [
    ({"pick": "9", "reason": "x", "cited": []}, "pick_not_in_candidates"),
    ({"pick": "2", "reason": "x", "cited": [{"candidate": "2", "field": "style", "value": "국물요리"}]}, "cited_value_mismatch"),
    ({"pick": "2", "reason": "x", "cited": [{"candidate": "2", "field": "rating", "value": "5"}]}, "cited_unknown_field"),
    ({"pick": "2", "reason": "x", "cited": []}, "uncited_override"),
    ({"pick": "1", "reason": "", "cited": []}, "no_reason"),
])
def test_a_bad_answer_falls_back_to_the_rule_first(answer, why):
    best, alternates = _three()
    pick = make_picker(FakeChat(answer))(best, alternates, _ctx("고기는 빼 주세요"))
    assert pick.by == "rule_fallback" and pick.failure == why and pick.best is best


def test_an_override_without_a_preference_is_refused_even_when_asked():
    """☆실측 — 취향 없이 부르면 gpt-4o-mini 가 id 를 순위로 착각해 2위를 골랐다. 서버가 막는다."""
    best, alternates = _three()
    always = lambda b, alts, ctx: [b, *alts]                                   # noqa: E731 — 평가의 「늘 부르기」
    pick = make_picker(FakeChat(GOOD), ask=always)(best, alternates, _ctx())
    assert pick.by == "rule_fallback" and pick.failure == "override_without_preference" and pick.best is best


def test_a_model_error_falls_back_without_raising():
    best, alternates = _three()
    pick = make_picker(FakeChat(error=TimeoutError("slow")))(best, alternates, _ctx("가볍게"))
    assert pick.by == "rule_fallback" and pick.failure == "call_failed:TimeoutError" and pick.best is best


def test_a_candidate_that_adds_more_travel_than_the_first_is_not_shown():
    """☆실측 — 취향으로 2위를 고르자 다음 일정에 더 늦었다(DA-003). 1등보다 이동이 느는 곳은 보이지 않는다."""
    best, alternates = _three(added_second=6)
    pool = should_ask(best, alternates, _ctx("고기는 빼 주세요"))
    assert [c.key for c in pool] == ["a", "c"]


def test_ids_are_the_rule_rank_and_facts_are_measured_values_only():
    best, alternates = _three()
    _, table = prompt([best, *alternates], _ctx("x"))
    assert list(table) == ["1", "2", "3"] and table["1"]["rule_rank"] == 1
    assert table["2"]["style"] == "한상차림" and table["3"]["likeness_to_original"] == "다른 종류"
    assert check(GOOD, table, preference="x") is None


def test_itinerary_change_records_who_picked():
    from app.domains.travel_ops.components.itinerary import itinerary_changes as changes
    from eval.runners.dining_alternatives import build, load_cases, DATASET

    case = next(c for c in load_cases(DATASET.with_name("dining_alternatives_pref_v1.jsonl")) if c["id"] == "DP-001")
    trip, items, places = build(case)
    meal = items[0]
    keys = {p["place_id"]: k for k, p in places.items()}
    pick_b = {"pick": "2", "reason": "채식 위주라 비빔밥집.", "cited": [{"candidate": "2", "field": "style", "value": "한상차림"}]}
    original = changes._leg_engine
    changes._leg_engine = lambda trip: None
    try:
        result = changes.plan_closed_on_day(trip=trip, items=items, places=list(places.values()), meal=meal, source="eval",
                                            detail="휴무", checked_at=NOON, meal_picker=make_picker(FakeChat(pick_b)))
        plain = changes.plan_closed_on_day(trip=trip, items=items, places=list(places.values()), meal=meal, source="eval",
                                           detail="휴무", checked_at=NOON)
    finally:
        changes._leg_engine = original
    new = result.replacements[meal.item_id]
    assert keys[str(new.place["place_id"])] == "B"
    assert new.detail["meal_pick"]["by"] == "llm"
    assert result.notice["other_options"][0] == "연탄불고기"                       # 규칙 1등은 「다른 안」으로 남는다
    old = plain.replacements[meal.item_id]
    assert keys[str(old.place["place_id"])] == "A" and "meal_pick" not in old.detail   # 선택기가 없으면 지금 그대로


# ── 연결 `[2026-10-15]` — 취향은 설문에서도 읽고, 선택기는 가드레일을 켰을 때만 꽂힌다 ──────────────

def test_preference_comes_from_the_survey_when_the_trip_has_no_explicit_sentence():
    from app.domains.travel_ops.components.planning.meal_pick import preference_of

    assert preference_of({"meal_preference": "매운 거 좋아해요"}) == "매운 거 좋아해요"
    assert preference_of({"survey": {"custom_answers": {"food": "국물 요리 위주로"}}}) == "국물 요리 위주로"
    assert preference_of({"survey": {"priority_details": {"food": ["michelin", "vegetarian", "nopo"]}}}) == "미쉐린 선정 식당 · 오래된 노포"
    assert preference_of({"survey": {"priority_details": {"food": ["vegetarian"]}}}) == ""      # 채식은 조건 — 취향이 아니다
    assert preference_of({}) == "" and preference_of(None) == ""


def test_the_picker_is_wired_only_when_the_guardrail_is_on(monkeypatch):
    from app import composition
    from app.core import settings as settings_module
    from app.infrastructure.llm_failover import OpenAIChat

    monkeypatch.setattr(settings_module, "dining_meal_pick", lambda: None)
    assert composition._dining_meal_picker() is None                               # 기본 꺼짐 — 규칙 1등

    made = []
    monkeypatch.setattr(settings_module, "dining_meal_pick", lambda: {"model": "openai:gpt-4o-mini"})
    monkeypatch.setattr(settings_module, "get_settings",
                        lambda: type("S", (), {"openai_api_key": "sk-test", "ollama_base_url": "", "ollama_model": ""})())
    from app.domains.travel_ops.components.planning import meal_pick
    # ★`[2026-10-16 사용자 결정]` 가드레일이 꽂는 것은 「흐름 한 칸」 선택기다 — 규칙 1위는 그대로 두고 다른 안 한 칸을 고른다
    monkeypatch.setattr(meal_pick, "make_flow_picker", lambda chat, **_: made.append(chat) or "picker")
    assert composition._dining_meal_picker() == "picker"
    assert isinstance(made[0], OpenAIChat) and made[0].model == "gpt-4o-mini"


def test_without_a_wired_picker_the_hook_answers_none():
    from app.domains.travel_ops.components.team_hooks import dining_ledger

    dining_ledger.clear()
    assert dining_ledger.meal_picker() is None



# ── 흐름 한 칸 `[2026-10-16 사용자 결정]` — 「LLM은 읽고 판단하고, 코드는 계산하고, 승인은 고객이」 ─────────────
# 대안 셋 = ①규칙 1위(그대로) ②**모델이 그날 흐름 · 취향으로 고른 안 하나**(이유와 함께) ③나머지.
# 모델은 1위를 바꾸지 않는다 — 고객이 고르는 목록에 성격이 다른 안을 하나 넣을 뿐이다. 취향 문장이 없어도 부른다(흐름이 근거).

FLOW_GOOD = {"pick": "3", "reason": "점심에 고기를 드셔서 가벼운 곳으로 골랐어요.",
             "cited": [{"candidate": "3", "field": "style", "value": "커피·차"}]}


def _day_ctx(preference: str = "") -> MealContext:
    return MealContext(meal_title="저녁", starts_at=NOON,
                       original={"name": "한우마당", "attributes": {"category": "한식", "style": "고기구이"}},
                       day=[{"time": "12:00", "kind": "dining", "title": "점심", "style": "고기구이"}],
                       preference=preference)


def test_the_flow_picker_keeps_the_rule_first_and_puts_its_pick_in_the_second_slot():
    from app.domains.travel_ops.components.planning.meal_pick import make_flow_picker

    best, alternates = _three()
    chat = FakeChat(FLOW_GOOD)
    pick = make_flow_picker(chat)(best, alternates, _day_ctx())            # 취향 문장 없이도 부른다
    assert pick.by == "llm" and pick.best is best                          # 1위는 그대로
    assert [c.key for c in pick.alternates] == ["c", "b"]                  # 고른 안이 둘째 칸
    assert pick.alternates[0].note.startswith("그날 흐름") and "가벼운" in pick.alternates[0].note
    shown = chat.calls[0][1]
    assert '"id": "1"' not in shown and '"id": "3"' in shown                # 1위는 모델에게 고르라고 보이지 않는다
    assert '"style": "고기구이"' in shown                                  # 그날 다른 식사(흐름)를 본다


@pytest.mark.parametrize("answer, why", [
    ({"pick": "1", "reason": "x", "cited": []}, "pick_not_in_candidates"),          # 1위는 후보가 아니다
    ({"pick": "3", "reason": "x", "cited": []}, "uncited_override"),               # 고른 곳의 사실을 인용해야 한다
    ({"pick": "3", "reason": "", "cited": [{"candidate": "3", "field": "style", "value": "커피·차"}]}, "no_reason"),
])
def test_a_bad_flow_answer_leaves_the_rule_order(answer, why):
    from app.domains.travel_ops.components.planning.meal_pick import make_flow_picker

    best, alternates = _three()
    pick = make_flow_picker(FakeChat(answer))(best, alternates, _day_ctx())
    assert pick.by == "rule_fallback" and pick.failure == why
    assert pick.best is best and [c.key for c in pick.alternates] == ["b", "c"] and not pick.alternates[0].note


def test_a_slightly_farther_place_is_still_offered_and_the_extra_walk_is_said_by_the_server():
    """☆`[2026-10-16 실제 모델 측정]` 「1위보다 이동이 늘지 않는 곳만」(10-13 의 1위 바꾸기 안전장치)을 옮겨 왔더니, 다른 안이 1~2분만 멀어도
    모두 빠져 흐름 사례 3건에서 모델을 한 번도 부르지 않았다. 둘째 칸은 고객이 고르는 안이라 그 조건을 뺐다 — 대신 늘어난 이동은
    **서버가 잰 값으로** 안 설명 끝에 붙인다(모델이 말하지 않아도 고객이 본다)."""
    from app.domains.travel_ops.components.planning.meal_pick import make_flow_picker

    best, alternates = _three(added_second=6)                              # 2위가 1위보다 6분 더 움직인다
    answer = {"pick": "2", "reason": "점심이 무거워서 비빔밥으로 골랐어요.",
              "cited": [{"candidate": "2", "field": "style", "value": "한상차림"}]}
    chat = FakeChat(answer)
    pick = make_flow_picker(chat)(best, alternates, _day_ctx())
    assert chat.calls and pick.by == "llm" and pick.best is best
    assert '"id": "2"' in chat.calls[0][1] and '"added_move_min": 6' in chat.calls[0][1]   # 모델도 늘어난 이동을 본다
    note = pick.alternates[0].note
    assert note.startswith("그날 흐름: 점심이 무거워서") and note.endswith("(1순위보다 이동 6분 더)"), note


def test_no_extra_walk_note_when_the_place_does_not_add_travel():
    from app.domains.travel_ops.components.planning.meal_pick import make_flow_picker

    best, alternates = _three()
    pick = make_flow_picker(FakeChat(FLOW_GOOD))(best, alternates, _day_ctx())
    assert "이동" not in pick.alternates[0].note.split("그날 흐름:", 1)[1].replace("가벼운 곳", "")


def test_the_flow_picker_is_not_called_without_two_others_in_the_same_route_band():
    """다음 일정에 늦지 않는 등급(동선 등급)이 1위와 다른 곳은 여전히 보이지 않는다 — 남는 다른 안이 하나면 부를 이유가 없다."""
    from app.domains.travel_ops.components.planning import meal_pick
    from app.domains.travel_ops.components.planning.meal_pick import make_flow_picker

    best, alternates = _three()
    far = alternates[0]
    original = meal_pick._route_band
    meal_pick._route_band = lambda c: (9,) if c is far else original(c)
    try:
        chat = FakeChat(FLOW_GOOD)
        pick = make_flow_picker(chat)(best, alternates, _day_ctx())
    finally:
        meal_pick._route_band = original
    assert pick.by == "rule" and chat.calls == [] and [c.key for c in pick.alternates] == ["b", "c"]


def test_the_flow_slot_shows_up_in_the_plan_and_in_the_question_to_the_customer():
    from uuid import uuid4

    from app.domains.travel_ops.components.itinerary import itinerary_changes as changes
    from app.domains.travel_ops.components.planning.meal_pick import make_flow_picker
    from app.domains.travel_ops.components.planning.pending import Decision, options_from, proposal_notice
    from eval.runners.dining_alternatives import build, load_cases, DATASET

    case = next(c for c in load_cases(DATASET.with_name("dining_alternatives_pref_v1.jsonl")) if c["id"] == "DP-001")
    trip, items, places = build(case)
    meal = items[0]
    keys = {p["place_id"]: k for k, p in places.items()}
    flow = {"pick": "2", "reason": "그날 흐름에 맞춰 가벼운 한상으로 골랐어요.",
            "cited": [{"candidate": "2", "field": "style", "value": "한상차림"}]}
    original = changes._leg_engine
    changes._leg_engine = lambda trip: None
    try:
        result = changes.plan_closed_on_day(trip=trip, items=items, places=list(places.values()), meal=meal, source="eval",
                                            detail="휴무", checked_at=NOON, meal_picker=make_flow_picker(FakeChat(flow)))
    finally:
        changes._leg_engine = original
    new = result.replacements[meal.item_id]
    assert keys[str(new.place["place_id"])] == "A"                                  # 규칙 1위 그대로
    first_alt = new.detail["alternates"][0]
    assert keys[str(first_alt["place_id"])] == "B" and first_alt["note"].startswith("그날 흐름"), first_alt
    options = options_from(result, meal)
    notice = proposal_notice(item=meal, decision=Decision("ask", "ask_first", None, False), causes=result.causes,
                             options=options, proposal_id=uuid4())
    assert "그날 흐름" in notice["text"], notice["text"]                            # 고객이 고를 때 이유가 보인다
