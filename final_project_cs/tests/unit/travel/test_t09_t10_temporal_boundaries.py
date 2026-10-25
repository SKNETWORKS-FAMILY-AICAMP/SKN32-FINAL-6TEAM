"""Acceptance T09/T10 (synthetic full49 rows) — structured temporal fields, no model.

The model answers below are the exact structured outputs the product E4B returned for the
synthetic acceptance sentences (full49 normal API run, no customer text). They are replayed
through the real decision and edit path; the model itself is not substituted for meaning.
"""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du
from app.domains.travel_ops.components.conversation.chat_edit import EditRefused, ops_for
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, tzinfo=KST)
T09 = "1월 2일 오후 3시 이후 일정만 한 시간 미뤄줘"
T10 = "N서울타워를 오후 11시 30분으로 미뤄줘"
T03 = "1월 2일 오전 11시 이후 일정들을 전부 한 시간 미뤄줘"


def items():
    names = ["북촌한옥마을", "인사동", "N서울타워", "국립중앙박물관"]
    return [Item(item_id=uuid4(), place_id=None, seq=n + 1, kind="activity", title=name,
                 starts_at=datetime(2030, 1, 2 + (n == 3), [10, 12, 15, 10][n], tzinfo=KST),
                 ends_at=datetime(2030, 1, 2 + (n == 3), [11, 13, 16, 11][n], 30 if n == 2 else 0, tzinfo=KST))
            for n, name in enumerate(names)]


def model_answer(case):
    base = {"target_change": "none", "destination_text": "", "condition_text": "", "at_day": "none", "steps": 0,
            "reads": [], "social": "", "general_requests": [], "choices": [],
            "place_search": {"relation": "none", "anchor_item": "i3", "place_text": "", "evidence": ""}}
    if case == "T09":
        return {**base, "action": "change_time",
                "time_edit": {"boundary": "shift", "scope": "range", "time": "", "duration_minutes": 0, "cascade": False,
                              "continue_previous": False, "evidence": T09},
                "anchor_kind": "time", "relation": "after",
                "query": {"day": "d1", "period": "all", "kind": "activity", "position": "all"},
                "target_item": "none", "fact": "none", "anchor_item": "none", "anchor_time": "15:00", "minutes": 60}
    if case == "T10":
        return {**base, "action": "change_time",
                "time_edit": {"boundary": "shift", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False,
                              "continue_previous": False, "evidence": T10},
                "target_item": "i3", "fact": "time", "condition_text": "오후 11시 30분으로 미뤄줘",
                "anchor_kind": "none", "anchor_item": "none", "anchor_time": "", "relation": "before", "minutes": 2340}
    raise AssertionError(case)


def decide(answer, message, source):
    class Chat:
        def structured(self, system, user, schema, **options):
            return dict(answer)
    return du.decide(Chat(), stops=du.stops_of(source), changes=[], history=[], selected_item_id=None,
                     message=message, now=NOW)


def test_t10_clock_minutes_are_not_a_relative_shift_size():
    # A clock's minute part ("11시 30분") is an absolute boundary, not "30분 미뤄".
    assert du.spoken_minutes(T10) is None
    assert du.spoken_minutes("인사동을 14시 50분으로 미뤄줘") is None
    # Existing relative sizes keep their meaning, including a size next to a clock.
    assert [du.spoken_minutes(m) for m in ("1시간 30분 미뤄줘", "한 시간 반 미뤄", "30분 늦춰줘", "오후 3시로")] == [90, 90, 30, None]
    assert du.spoken_minutes("오후 3시 30분 이후 일정을 1시간 미뤄줘") == 60
    assert du.spoken_minutes("11시30분 일정을 20분 미뤄줘") == 20


def test_t10_observed_relative_answer_does_not_save_a_fabricated_delta():
    source = items()
    decision = decide(model_answer("T10"), T10, source)
    assert decision.action == "change_time" and decision.item is source[2]
    assert decision.minutes is None                     # was +30 taken from "11시 30분"
    with pytest.raises(EditRefused) as refused:
        ops_for(decision, items=source, now=NOW, message=T10)
    assert refused.value.code.startswith("need_")       # public status clarify; nothing saved


def test_t10_absolute_start_still_refuses_to_cross_midnight():
    source = items()
    answer = model_answer("T10")
    answer.update(minutes=0, time_edit={**answer["time_edit"], "boundary": "start", "time": "23:30"})
    decision = decide(answer, T10, source)
    with pytest.raises(EditRefused) as refused:
        ops_for(decision, items=source, now=NOW, message=T10)
    assert refused.value.code == "crosses_midnight" or "자정" in refused.value.message


def test_t09_item_starting_exactly_at_the_time_boundary_is_asked_not_guessed():
    source = items()
    decision = decide(model_answer("T09"), T09, source)
    assert decision.minutes == 60 and decision.raw["anchor_time"] == "15:00"
    with pytest.raises(EditRefused) as refused:
        ops_for(decision, items=source, now=NOW, message=T09)
    assert refused.value.code == "need_time_boundary"   # need_ → public status clarify
    assert "N서울타워" in refused.value.message and "15:00" in refused.value.message


@pytest.mark.parametrize("relation,clock", [("before", "15:00"), ("after", "12:00")])
def test_boundary_question_applies_to_both_range_directions(relation, clock):
    source = items()
    answer = model_answer("T09")
    answer.update(relation=relation, anchor_time=clock)
    message = T09.replace("오후 3시", "오후 3시" if clock == "15:00" else "낮 12시").replace("이후", "이후" if relation == "after" else "이전")
    answer["time_edit"] = {**answer["time_edit"], "evidence": message}
    decision = decide(answer, message, source)
    with pytest.raises(EditRefused) as refused:
        ops_for(decision, items=source, now=NOW, message=message)
    assert refused.value.code == "need_time_boundary"


def test_t03_range_without_an_item_on_the_boundary_still_moves_exact_targets():
    source = items()
    answer = model_answer("T09")
    answer.update(anchor_time="11:00")
    answer["time_edit"] = {**answer["time_edit"], "evidence": T03}
    decision = decide(answer, T03, source)
    ops, _ = ops_for(decision, items=source, now=NOW, message=T03)
    assert [(o.item_id, o.starts_at, o.ends_at) for o in ops] == [
        (source[1].item_id, "13:00", "14:00"), (source[2].item_id, "16:00", "17:30")]
