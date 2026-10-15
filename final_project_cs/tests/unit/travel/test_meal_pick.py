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
    monkeypatch.setattr(meal_pick, "make_picker", lambda chat, **_: made.append(chat) or "picker")
    assert composition._dining_meal_picker() == "picker"
    assert isinstance(made[0], OpenAIChat) and made[0].model == "gpt-4o-mini"


def test_without_a_wired_picker_the_hook_answers_none():
    from app.domains.travel_ops.components.team_hooks import dining_ledger

    dining_ledger.clear()
    assert dining_ledger.meal_picker() is None
