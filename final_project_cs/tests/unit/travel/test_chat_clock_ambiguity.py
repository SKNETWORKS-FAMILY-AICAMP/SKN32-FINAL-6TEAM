"""시각 바꾸기 인용에 서로 다른 시각이 둘 이상 — 모델이 하나를 골라 저장하지 않고 되묻는다(수용 X02, 2026-10-26 묶음 L).

★코드는 어느 시각이 맞는지 고르지 않는다. 「모델이 낸 인용(evidence)이 모델 값을 하나로 정하는가」만 본다 —
  `validate` 가 이미 인용에서 시각을 다시 계산하는 것(`fact_check.recompute_time`)을 인용 안의 시각 언급마다 돌려,
  서로 다른 값이 나오면 그 인용은 값을 정하지 못한 것이다(Codex E2 = A, 보수적: 기준 시각 · 기간 끝으로 빼 주지 않는다).
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import edit_intent
from app.domains.travel_ops.components.conversation.decision_unit import decide, stops_of
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, 0, tzinfo=KST)
X02 = "인사동을 오후 1시로 바꾸면서 동시에 낮 12시로 해줘"


def stop(title, start, end, seq, day=0):
    base = datetime(2030, 1, 2, tzinfo=KST) + timedelta(days=day)
    place = {"place_id": uuid4(), "name": title, "kind": "activity", "latitude": 37.57, "longitude": 126.98,
             "attributes": {"hours": ["00:00", "23:59"]}}
    return Item(item_id=uuid4(), seq=seq, kind="activity", title=title, place_id=place["place_id"], place=place,
                starts_at=base.replace(hour=start[0], minute=start[1]), ends_at=base.replace(hour=end[0], minute=end[1]))


def plan():
    return [stop("북촌한옥마을", (10, 0), (11, 0), 1), stop("인사동", (12, 0), (13, 0), 2),
            stop("N서울타워", (15, 0), (16, 30), 3), stop("국립중앙박물관", (10, 0), (11, 0), 4, day=1)]


def x02_raw(**over):
    """J 실 E4B 2차(acceptance49-J-20261026 J-real-729a3ed3-02-localstream) X02 원출력과 같은 모양."""
    raw = {"fact": "none", "reads": [], "steps": 1, "action": "change_time", "at_day": "none", "social": "",
           "choices": [], "minutes": 0, "relation": "before",
           "time_edit": {"time": "13:00", "scope": "item", "cascade": False, "boundary": "start", "evidence": X02,
                         "duration_minutes": 0, "continue_previous": False},
           "anchor_item": "i2", "anchor_kind": "time", "anchor_time": "13:00", "target_item": "i2",
           "place_search": {"evidence": "", "relation": "none", "place_text": "", "anchor_item": "i2"},
           "place_setting": {"want": "any", "evidence": ""}, "target_change": "none", "condition_text": "",
           "destination_text": "", "general_requests": []}
    raw.update(over)
    return raw


def decided(raw, message):
    items = plan()
    model = SimpleNamespace(structured=lambda *a, **k: dict(raw))
    return items, decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=None, message=message, now=NOW)


def with_edit(evidence, time, message, **edit):
    raw = x02_raw()
    raw["time_edit"] = {**raw["time_edit"], "evidence": evidence, "time": time, **edit}
    raw["anchor_time"] = time
    return decided(raw, message)


def test_recorded_x02_raw_is_asked_back_not_saved_at_one_of_the_two_times():
    from app.domains.travel_ops.components.conversation.trip_messages import _clarify_with_choices

    items, got = decided(x02_raw(), X02)
    assert got.action == "change_time" and got.item.title == "인사동"          # 해석 자체는 그대로 통과한다(실패 아님)
    asked = edit_intent.ask_on_clock_ambiguity(got)
    assert asked.action == "clarify" and asked.choices == []
    assert asked.raw["clock_ambiguity"] == {"reason": "multiple_clocks", "clocks": ["12:00", "13:00"], "time": "13:00",
                                            "evidence": X02}
    reply = _clarify_with_choices(asked, items, lead=asked.question)
    assert reply == {"status": "clarify", "text": asked.question}            # 다른 일정 「다른 곳으로」 목록을 붙이지 않는다
    assert "12:00" in reply["text"] and "13:00" in reply["text"] and "일정은 바꾸지 않았어요" in reply["text"]
    assert "인사동" in reply["text"]


@pytest.mark.parametrize("evidence,message", [
    ("오후 1시로", X02),                                                   # 모델이 값의 인용만 냈다 — 하나로 정해진다
    ("오후 1시, 그러니까 1시로", "인사동을 오후 1시, 그러니까 1시로 옮겨줘"),   # 같은 시각을 두 번 — 값은 하나
    ("1시간 늦춘 1시로", "인사동을 1시간 늦춘 1시로 옮겨줘"),                  # 「1시간」은 길이다(시각 아님)
    ("13:00으로", "인사동을 13:00으로 옮겨줘"),
])
def test_a_quote_that_fixes_one_time_is_left_alone(evidence, message):
    _, got = with_edit(evidence, "13:00", message)
    assert edit_intent.clock_ambiguity(got) is None and edit_intent.ask_on_clock_ambiguity(got) is got


@pytest.mark.parametrize("evidence,time", [
    ("12시에 있는 인사동을 1시로 옮겨줘", "13:00"),     # 지금 시작 시각과 같은 기준 언급도 빼 주지 않는다(Codex E2 — 역할이 입증되지 않음)
    ("1시 말고 2시로 옮겨줘", "14:00"),                 # 정정 표현 — 고르지 않고 묻는다
    ("3시 N서울타워 가기 전에 인사동을 1시로", "13:00"),  # 다른 일정의 시각
    ("1시부터 3시까지로 바꿔줘", "13:00"),              # 기간 끝도 관계가 검증되지 않으면 빼 주지 않는다
])
def test_other_clock_mentions_in_the_quote_are_asked_back_conservatively(evidence, time):
    # 인용의 **첫** 시각이 모델 값과 다르면 종전 `validate` 가 이미 해석 실패로 막는다(아래 시험) — 여기서는 그 관문을 지난
    #   모양(첫 시각 = 모델 값이거나, 다른 경로로 만들어진 결정)에서도 이 검사가 따로 묻는지 본다
    from app.domains.travel_ops.components.conversation.decision_unit import Decision

    raw = x02_raw()
    raw["time_edit"] = {**raw["time_edit"], "evidence": evidence, "time": time}
    got = Decision(action="change_time", item=plan()[1], change=None, fact="none", minutes=None, question="", raw=raw)
    found = edit_intent.clock_ambiguity(got)
    assert found is not None and len(found["clocks"]) >= 2 and time in found["clocks"]
    assert edit_intent.ask_on_clock_ambiguity(got).action == "clarify"


@pytest.mark.parametrize("evidence,time", [("12시에 있는 인사동을 1시로 옮겨줘", "13:00"), ("1시 말고 2시로 옮겨줘", "14:00")])
def test_a_first_quoted_clock_that_disagrees_is_still_a_decision_failure(evidence, time):
    from app.domains.travel_ops.components.conversation.decision_unit import DecisionFailed

    with pytest.raises(DecisionFailed, match="temporal clock disagrees with evidence"):
        with_edit(evidence, time, "인사동을 " + evidence)


def test_relative_moves_and_range_shifts_without_an_absolute_time_are_not_checked():
    raw = x02_raw(anchor_kind="none", anchor_time="", minutes=60)
    raw["time_edit"] = {**raw["time_edit"], "boundary": "shift", "time": "", "evidence": "12시 인사동 한 시간 늦춰줘"}
    _, got = decided(raw, "12시 인사동 한 시간 늦춰줘")
    assert edit_intent.clock_ambiguity(got) is None


def test_place_actions_whose_time_edit_is_not_executed_are_not_checked():
    from app.domains.travel_ops.components.conversation.decision_unit import Decision

    raw = x02_raw(action="apply_change", destination_text="덕수궁")
    items = plan()
    got = Decision(action="apply_change", item=items[1], change=None, fact="none", minutes=None, question="", raw=raw)
    assert edit_intent.clock_ambiguity(got) is None
