"""장소 행동에 실행할 수 없는 시간 수정이 붙은 해석 — 해석 실패도 장소 교체도 아니라 되묻기(2026-10-26 T16 실 E4B 재생)."""
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
MESSAGE = "네, 제안한 일정 변경을 승인해요"


def stop(title, start, end, seq, day=0):
    base = datetime(2030, 1, 2, tzinfo=KST) + timedelta(days=day)
    place = {"place_id": uuid4(), "name": title, "kind": "activity", "latitude": 37.57, "longitude": 126.98,
             "attributes": {"hours": ["00:00", "23:59"]}}
    return Item(item_id=uuid4(), seq=seq, kind="activity", title=title, place_id=place["place_id"], place=place,
                starts_at=base.replace(hour=start[0], minute=start[1]), ends_at=base.replace(hour=end[0], minute=end[1]))


def plan():
    return [stop("북촌한옥마을", (10, 0), (11, 0), 1), stop("인사동", (12, 0), (13, 0), 2),
            stop("N서울타워", (15, 0), (16, 30), 3), stop("국립중앙박물관", (10, 0), (11, 0), 4, day=1)]


def recorded_raw(**over):
    """integ-v10 real2/real6 T16 에서 E4B 가 낸 해석(reallogs/real2-T16-raw.json)과 같은 모양."""
    raw = {"action": "apply_change",
           "time_edit": {"boundary": "shift", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False,
                         "continue_previous": True, "evidence": MESSAGE},
           "place_search": {"relation": "none", "anchor_item": "i3", "place_text": "", "evidence": ""},
           "place_setting": {"want": "any", "evidence": ""}, "target_item": "i3", "target_change": "none", "fact": "none",
           "destination_text": "", "condition_text": "", "anchor_kind": "item", "anchor_item": "i3", "anchor_time": "",
           "at_day": "none", "relation": "after", "steps": 1, "minutes": 60, "reads": [], "social": "",
           "general_requests": [], "choices": []}
    raw.update(over)
    return raw


def aliases():
    return {"none", "i1", "i2", "i3", "i4"}


def test_unexecuted_time_edit_on_a_place_action_is_not_a_decision_failure():
    edit_intent.validate(recorded_raw(), MESSAGE, aliases())          # 실행되지 않는 칸의 조합은 해석 전체를 버리지 않는다


@pytest.mark.parametrize("over", [{"action": "change_time"}, {"change_scope": "time"}, {"change_scope": "date"}])
def test_executed_time_edit_keeps_the_consistency_check(over):
    with pytest.raises(ValueError, match="inconsistent temporal scope"):
        edit_intent.validate(recorded_raw(**over), MESSAGE, aliases())


@pytest.mark.parametrize("evidence", ["없는 인용", ""])
def test_quote_check_still_applies_to_a_place_action(evidence):
    raw = recorded_raw()
    raw["time_edit"] = {**raw["time_edit"], "evidence": evidence}
    with pytest.raises(ValueError, match="unquoted time_edit"):
        edit_intent.validate(raw, MESSAGE, aliases())


def test_recorded_t16_raw_becomes_a_question_not_a_swap():
    from app.domains.travel_ops.components.conversation.trip_messages import _clarify_with_choices

    items = plan()
    model = SimpleNamespace(structured=lambda *a, **k: recorded_raw())
    got = decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=items[2].item_id,  # 화면에서 고른 대상
                 message=MESSAGE, now=NOW)
    assert got.action == "apply_change" and got.item.item_id == items[2].item_id
    asked = edit_intent.ask_on_conflict(got)
    assert asked.action == "clarify" and asked.raw["temporal_conflict"]["continue_previous"] is True
    reply = _clarify_with_choices(asked, items, lead=asked.question)
    assert reply["text"].startswith("「N서울타워」을(를) 다른 곳으로 바꿀지, 시각을 옮길지")
    assert "일정은 바꾸지 않았어요" in reply["text"]
    assert [c["action"] for c in reply["choices"]] == ["apply_change"]
    assert reply["choices"][0]["item_id"] == str(items[2].item_id)


def test_time_only_place_action_asks_instead_of_swapping():
    """실 E4B D04(2026-10-26) 「N서울타워를 1월 3일 오후 2시에 가는 걸로 바꿔줘」 → apply_change + start 14:00 · d2 → 덕수궁으로 바뀌었다.
    새 장소 이름·조건 없이 시각만 있으면 바꾸지 않고 묻는다."""
    items = plan()
    message = "N서울타워를 1월 3일 오후 2시에 가는 걸로 바꿔줘"
    raw = recorded_raw(at_day="d2", anchor_kind="time", anchor_time="14:00", minutes=0)
    raw["time_edit"] = {**raw["time_edit"], "boundary": "start", "time": "14:00", "continue_previous": False,
                        "evidence": "1월 3일 오후 2시에 가는 걸로"}
    model = SimpleNamespace(structured=lambda *a, **k: dict(raw))
    got = decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=items[2].item_id,
                 message=message, now=NOW)
    assert got.action == "apply_change"
    asked = edit_intent.ask_on_conflict(got)
    assert asked.action == "clarify" and asked.raw["temporal_conflict"]["reason"] == "time_without_place"


@pytest.mark.parametrize("over", [{"destination_text": "덕수궁"}, {"place_setting": {"want": "outdoor", "evidence": "야외로"}}])
def test_place_named_or_conditioned_with_time_is_left_alone(over):
    """새 장소(이름 · 실내외 조건)를 말했으면 시각이 함께 있어도 장소 요청이다 — 되묻지 않는다."""
    from app.domains.travel_ops.components.conversation.decision_unit import Decision

    items = plan()
    raw = recorded_raw(**over)
    raw["time_edit"] = {**raw["time_edit"], "continue_previous": False}
    got = Decision(action="apply_change", item=items[2], change=None, fact="none", minutes=None, question="", raw=raw)
    assert edit_intent.temporal_conflict(got) is None and edit_intent.ask_on_conflict(got) is got


def test_consistent_place_and_shift_without_new_place_still_asks():
    items = plan()
    raw = recorded_raw()
    raw["time_edit"] = {**raw["time_edit"], "continue_previous": False}
    model = SimpleNamespace(structured=lambda *a, **k: dict(raw))
    got = decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=items[2].item_id,  # 화면에서 고른 대상
                 message=MESSAGE, now=NOW)
    assert edit_intent.temporal_conflict(got)["reason"] == "time_without_place"


def test_change_time_is_never_turned_into_a_place_question():
    items = plan()
    from app.domains.travel_ops.components.conversation.decision_unit import Decision

    got = Decision(action="change_time", item=items[2], change=None, fact="none", minutes=None, question="",
                   raw={"time_edit": recorded_raw()["time_edit"]})
    assert edit_intent.temporal_conflict(got) is None
