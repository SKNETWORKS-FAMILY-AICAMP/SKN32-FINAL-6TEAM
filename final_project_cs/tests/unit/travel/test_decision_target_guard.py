# -*- coding: utf-8 -*-
"""결정 단위 — 문장이 가리키지 않은 일정을 모델이 짐작으로 바꾸게 두지 않는다(`guard_target`). `[2026-10-06 사용자 지시 — 엉뚱한 대상 변경 0건]`

★사고 기록: 재생 시험(2026-09-30) 7일 여행에서 「저녁 식당 바꿔 줘」(화면에서 고른 일정 = 4일차 활동)를 모델이 **3일차**(i35) 저녁 식당으로 바꾸기로 했다. 정답은 고른 날의 저녁 식당(i23)이거나 되묻기다.
이 시험의 「모델」은 그 사고의 출력을 그대로 돌려주는 흉내다(실제 모델의 비결정성에 기대지 않는다) — 실제 모델 재생 결과는 `eval/decision_unit/replay.py`.

지키려는 것
 ①근거 없는 대상(날을 말하지 않았고 이름도 없고 화면 선택도 아닌데 약속의 날이 아닌 곳)은 **바꾸지 않고 되묻는다** — 후보는 같은 종류 · 같은 끼니, 약속의 날 가까운 순 3곳이다
 ②근거가 있으면 건드리지 않는다 — 화면에서 고른 일정 · 일정 이름 · 직전 대화나 가장 최근 변경 · 날/순서/때를 가리키는 말 · 같은 종류가 하나뿐 · 날을 말하지 않은 약속(고른 날 · 1일차)과 같다
 ③바꾸는 할 일(`apply_change` · `propose_alternatives` · `report_closed`)에만 건다 — 사실 질문 · 되돌리기는 그대로
 ④되묻기로 바뀌어도 Case 에 이유(`raw.guard`)가 남는다

재현:

    python -m pytest tests/unit/travel/test_decision_target_guard.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.domains.travel_ops.components.conversation.decision_unit import decide, stops_of
from eval.decision_unit.replay import load_trips

TRIPS = load_trips(Path(__file__).resolve().parents[3] / "eval" / "decision_unit" / "trips.json")


class _Model:
    """해석 모델 흉내 — 정해 둔 한 줄을 그대로 돌려준다."""

    def __init__(self, action, target, **extra):
        self.answer = {"action": action, "target_item": target, "target_change": extra.pop("change", "none"), "fact": extra.pop("fact", "none"),
                       "minutes": 0, "choices": []}

    def structured(self, system, user, schema, *, num_predict=160):
        return dict(self.answer)


def _run(trip, message, action, target, *, selected=None, history=(), **extra):
    items, changes = TRIPS[trip]
    stops = stops_of(items)
    selected_id = next((s.item.item_id for s in stops if s.alias == selected), None)
    got = decide(_Model(action, target, **extra), stops=stops, changes=changes, history=list(history), selected_item_id=selected_id, message=message)
    alias_of = {s.item.item_id: s.alias for s in stops}
    return got, alias_of


# ── ① 사고 기록 ───────────────────────────────────────────────────
def test_the_recorded_failure_a_dinner_on_another_day_is_asked_about_not_changed():
    got, alias = _run("long7", "저녁 식당 바꿔 줘", "apply_change", "i35", selected="i22")        # 모델이 3일차 저녁 식당(i35)을 골랐다
    assert got.action == "clarify" and got.item is None and got.change is None
    asked = [alias[c["item"].item_id] for c in got.choices]
    assert asked[0] == "i23" and "i35" in asked                                                   # 고른 날(11-05)의 저녁 식당이 첫 후보 · 모델이 본 해석(i35)도 후보로 남는다
    assert len(asked) == 3 and all(c["action"] == "apply_change" for c in got.choices)
    assert all(c["item"].kind == "dining" and c["item"].starts_at.hour == 18 for c in got.choices)  # 같은 종류 · 같은 끼니
    assert got.raw["guard"] == {"ambiguous_target": "i35", "asked": asked}                         # ④ 이유가 남는다


def test_a_pick_on_the_promised_day_is_kept_even_when_the_sentence_names_no_day():
    got, alias = _run("long7", "저녁 식당 바꿔 줘", "apply_change", "i23", selected="i22")        # 약속(고른 날)과 같다
    assert got.action == "apply_change" and alias[got.item.item_id] == "i23" and "guard" not in got.raw
    two_days, alias = _run("e71ee6ab", "저녁 식당 바꿔 줘", "apply_change", "i5")                  # 고른 일정이 없으면 1일차 — 실제 대화 문장
    assert two_days.action == "apply_change" and alias[two_days.item.item_id] == "i5"


def test_without_a_selection_a_pick_on_a_later_day_is_asked_about():
    got, alias = _run("e71ee6ab", "저녁 식당 바꿔 줘", "apply_change", "i10")                       # 2일차 저녁 식당 — 날을 말하지 않았다
    assert got.action == "clarify" and [alias[c["item"].item_id] for c in got.choices] == ["i5", "i10"]


def test_several_activities_on_the_promised_day_are_still_a_guess():
    got, alias = _run("e71ee6ab", "활동 하나 바꿔 줘", "apply_change", "i2")                        # 1일차 활동이 둘(i2 · i4) — 어느 것인지 말하지 않았다
    assert got.action == "clarify" and {alias[c["item"].item_id] for c in got.choices} >= {"i2", "i4"}


# ── ② 근거가 있으면 건드리지 않는다 ───────────────────────────────
@pytest.mark.parametrize("trip,message,action,target,selected,history", [
    ("long7", "이거 다른 데로 바꿔 줘", "apply_change", "i34", "i34", ()),                          # 화면에서 고른 일정
    ("long7", "금돼지식당 오늘 휴무래", "report_closed", "i17", None, ()),                          # 이름
    ("long7", "전쟁기념관 문 닫았대요", "report_closed", "i28", None, ()),
    ("long7", "한강 달빛무지개분수 말고 다른 거 추천해줘", "propose_alternatives", "i12", None, ()),   # 「한강」 두 글자만 겹치는 곳(여의도 한강공원)이 있어도 이름이 가장 많이 겹치는 곳이 그것이다
    ("long7", "3일차 점심 식당 바꿔 줘", "apply_change", "i15", None, ()),                          # 날
    ("long7", "마지막 날 첫 활동 바꿔", "apply_change", "i38", None, ()),                           # 순서
    ("long7", "7일차 마지막 일정 바꿔", "apply_change", "i42", None, ()),
    ("long7", "셋째 날 세 번째 식당 바꿔", "apply_change", "i17", None, ()),
    ("long7", "다음 식당 바꿔 줘", "apply_change", "i29", None, ()),                                # 때
    ("long7", "거기 말고 다른 데로 바꿔줘", "apply_change", "i28", None,                            # 직전 대화에 나온 곳(전쟁기념관)
     [{"role": "assistant", "text": "11-06 14:00 전쟁기념관 가는 길이에요"}]),
])
def test_a_pick_with_a_basis_is_not_second_guessed(trip, message, action, target, selected, history):
    got, alias = _run(trip, message, action, target, selected=selected, history=history)
    assert got.action == action and alias[got.item.item_id] == target and "guard" not in got.raw


def test_when_the_name_overlap_is_a_tie_the_pick_still_needs_a_basis_and_stays_among_the_candidates():
    """「한강」만 말하면 한강이 든 곳이 둘이다(i12 · i36) — 모델이 하나를 골라도 짐작이다. 되묻되 모델이 본 해석도 후보로 남긴다."""
    for pick in ("i12", "i36"):
        got, alias = _run("long7", "한강 쪽 바꿔 줘", "apply_change", pick)
        assert got.action == "clarify" and pick in {alias[c["item"].item_id] for c in got.choices} and len(got.choices) == 3


def test_the_same_pronoun_without_any_talk_about_that_place_is_asked_about():
    got, _ = _run("long7", "거기 말고 다른 데로 바꿔줘", "apply_change", "i28", history=[])
    assert got.action == "clarify" and got.raw["guard"]["ambiguous_target"] == "i28"               # 「거기」가 어디인지 대화에도 없다 — 활동이 여럿이라 짐작이다


def test_the_latest_change_is_a_basis_for_a_pronoun():
    items, changes = TRIPS["long7"]
    stops = stops_of(items)
    target = next(s for s in stops if s.item.item_id == changes[-1].target_item_id)
    got = decide(_Model("apply_change", target.alias), stops=stops, changes=changes, history=[], selected_item_id=None, message="방금 바꾼 곳 말고 다른 데로")
    assert got.action == "apply_change" and got.item is target.item


def test_two_lunches_need_a_basis_and_the_only_lunch_does_not():
    items, changes = TRIPS["e71ee6ab"]
    got, _ = _run("e71ee6ab", "점심 식당 바꿔 줘", "apply_change", "i8")                            # 점심이 둘(1 · 2일차) — 2일차를 골랐다
    assert got.action == "clarify"
    one_day = stops_of(items[:5])                                                                   # 1일차만 — 점심이 하나뿐이다
    alone = decide(_Model("apply_change", "i3"), stops=one_day, changes=changes, history=[], selected_item_id=None, message="점심 식당 바꿔 줘")
    assert alone.action == "apply_change" and alone.item is one_day[2].item


# ── ③ 바꾸는 할 일에만 ────────────────────────────────────────────
def test_questions_and_rollbacks_are_not_guarded():
    got, _ = _run("long7", "저녁 식당 어디야", "answer_fact", "i35", fact="address")
    assert got.action == "answer_fact" and got.item is not None                                     # 사실 질문은 잘못 짚어도 잃는 것이 없다(`fact_first`)
    rolled, _ = _run("long7", "원래대로 돌려줘", "rollback", "none", change="c3")
    assert rolled.action == "rollback" and rolled.change is not None
    no_target, _ = _run("long7", "저녁 식당 바꿔 줘", "apply_change", "none")                       # 대상을 못 골랐으면 부르는 쪽이 원래 되묻는다
    assert no_target.action == "apply_change" and no_target.item is None
