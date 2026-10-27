"""시간 변경의 범위 기준 시각(「오후 2시 이전」)을 한 일정의 새 시작으로 쓰지 않는다 — 되묻는다(수용 T04, 2026-10-26 fix5).

☆실 E4B(tripilot-pointer:e4b-ft, temperature 0) 원출력(J 2차 · rm9 재시험 두 번 같음):
  「1월 2일 오후 2시 이전 일정들을 전부 한 시간 당겨줘」 → change_time · target_item=i2(인사동) · time_edit={start, item, time ""} ·
  anchor_kind=time · anchor_time=14:00 · relation=before. `time_ops` 가 「구형 시작 시각 칸」으로 넘기고 `chat_edit.ops_for` 가
  anchor_time 을 새 시작으로 써 **인사동을 14:00 으로 옮기려 했다**(옮길 크기 -60 은 버려짐). 이번엔 N서울타워와 겹쳐 거절됐지만
  겹치지 않으면 고객이 말하지 않은 시각으로 저장된다.
★계약: change_time 의 새 시작은 relation=at 의 anchor_time(`decision_unit.SYSTEM`), relation before/after 의 anchor_time 은
  범위 기준 시각이다(`edit_intent.SYSTEM` 「기준 시각은 옮길 새 시작이나 종료가 아니므로」). 코드는 범위로 고쳐 실행하지 않는다
  (출력 수리 금지 — Codex fix5 G2) — 한 일정인지 범위인지 되묻고 일정은 그대로 둔다.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import chat_edit, edit_intent
from app.domains.travel_ops.components.conversation.chat_edit import EditRefused
from app.domains.travel_ops.components.conversation.decision_unit import decide, stops_of
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, 0, tzinfo=KST)
T04 = "1월 2일 오후 2시 이전 일정들을 전부 한 시간 당겨줘"


def stop(title, start, end, seq, day=0):
    base = datetime(2030, 1, 2, tzinfo=KST) + timedelta(days=day)
    place = {"place_id": uuid4(), "name": title, "kind": "activity", "latitude": 37.57, "longitude": 126.98,
             "attributes": {"hours": ["00:00", "23:59"]}}
    return Item(item_id=uuid4(), seq=seq, kind="activity", title=title, place_id=place["place_id"], place=place,
                starts_at=base.replace(hour=start[0], minute=start[1]), ends_at=base.replace(hour=end[0], minute=end[1]))


def plan():
    return [stop("북촌한옥마을", (10, 0), (11, 0), 1), stop("인사동", (12, 0), (13, 0), 2),
            stop("N서울타워", (15, 0), (16, 30), 3), stop("국립중앙박물관", (10, 0), (11, 0), 4, day=1)]


def t04_raw(**over):
    """J 실 E4B 2차(acceptance49-J-20261026 J-real-729a3ed3-02-localstream · J-real-rm9-74b2b232-T04X02F03) T04 원출력 그대로."""
    raw = {"fact": "schedule", "reads": [], "steps": 1, "action": "change_time", "at_day": "d1", "social": "",
           "choices": [{"fact": "schedule", "action": "change_time", "target_item": "i2", "target_change": "none"}],
           "minutes": 0, "relation": "before",
           "time_edit": {"time": "", "scope": "item", "cascade": True, "boundary": "start", "evidence": T04,
                         "duration_minutes": 0, "continue_previous": False},
           "anchor_item": "none", "anchor_kind": "time", "anchor_time": "14:00", "target_item": "i2",
           "place_search": {"evidence": "", "relation": "none", "place_text": "", "anchor_item": "none"},
           "place_setting": {"want": "any", "evidence": ""}, "target_change": "none", "condition_text": "오후 2시 이전",
           "destination_text": "", "general_requests": []}
    raw.update(over)
    return raw


def decided(raw, message=T04):
    items = plan()
    model = SimpleNamespace(structured=lambda *a, **k: dict(raw))
    return items, decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=None, message=message, now=NOW)


def test_recorded_t04_raw_is_asked_back_instead_of_moving_one_stop_to_the_range_boundary():
    from app.domains.travel_ops.components.conversation.trip_messages import _clarify_with_choices

    items, got = decided(t04_raw())
    assert got.action == "change_time" and got.item.title == "인사동" and got.minutes == -60   # 해석은 통과한다(실패 아님)
    asked = edit_intent.ask_on_range_anchor(got)
    assert asked.action == "clarify" and asked.choices == []
    assert asked.raw["range_anchor_conflict"] == {"reason": "range_boundary_on_one_item", "anchor_time": "14:00",
                                                  "relation": "before", "scope": "item", "boundary": "start"}
    reply = _clarify_with_choices(asked, items, lead=asked.question)
    assert reply == {"status": "clarify", "text": asked.question}
    assert "인사동" in reply["text"] and "14:00 이전" in reply["text"] and "일정은 바꾸지 않았어요" in reply["text"]


def test_the_range_boundary_is_never_used_as_a_new_start_even_if_the_ask_is_bypassed():
    """방어(Codex fix5 G2): `ops_for` 의 「구형 시작 시각 칸」 분기는 relation=at 일 때만 새 시작이다 — 전에는 인사동 → 14:00."""
    items, got = decided(t04_raw())
    with pytest.raises(EditRefused) as refused:
        chat_edit.ops_for(got, items=items, now=NOW, message=T04)
    assert refused.value.code == "need_target"
    assert "14:00 이전" in refused.value.message and "인사동" in refused.value.message


@pytest.mark.parametrize("relation", ["after"])
def test_after_boundary_is_asked_back_too(relation):
    message = "1월 2일 오후 2시 이후 일정들을 전부 한 시간 당겨줘"
    _, got = decided(t04_raw(relation=relation, condition_text="오후 2시 이후",
                             time_edit={**t04_raw()["time_edit"], "evidence": message}), message)
    asked = edit_intent.ask_on_range_anchor(got)
    assert asked.action == "clarify" and asked.raw["range_anchor_conflict"]["relation"] == "after"
    assert "14:00 이후" in asked.question


def test_a_new_start_clock_at_the_time_is_still_moved_there():
    """relation=at 의 anchor_time 은 새 시작 — 「인사동을 오후 2시로 옮겨줘」는 그대로 14:00 으로 옮긴다(회귀 방지)."""
    message = "인사동을 오후 2시로 옮겨줘"
    items, got = decided(t04_raw(relation="at", condition_text="",
                                 time_edit={**t04_raw()["time_edit"], "evidence": message, "cascade": False}), message)
    assert edit_intent.ask_on_range_anchor(got) is got
    ops, _ = chat_edit.ops_for(got, items=items, now=NOW, message=message)
    assert [(op.starts_at, op.ends_at) for op in ops] == [("14:00", "15:00")]


def test_a_validated_range_shift_with_the_same_boundary_is_not_touched():
    raw = t04_raw(target_item="none", choices=[], fact="none",
                  query={"day": "d1", "period": "all", "kind": "all", "position": "all"},
                  time_edit={"time": "", "scope": "range", "cascade": False, "boundary": "shift", "evidence": T04,
                             "duration_minutes": 0, "continue_previous": False}, minutes=-60)
    items, got = decided(raw)
    assert edit_intent.ask_on_range_anchor(got) is got
    ops, _ = chat_edit.ops_for(got, items=items, now=NOW, message=T04)
    assert sorted((op.starts_at, op.ends_at) for op in ops) == [("09:00", "10:00"), ("11:00", "12:00")]


def test_non_time_actions_are_not_touched():
    _, got = decided(t04_raw(action="answer_fact", fact="schedule", choices=[],
                             time_edit={**t04_raw()["time_edit"], "boundary": "none", "evidence": ""},
                             query={"day": "d1", "period": "all", "kind": "all", "position": "all"}, target_item="none"),
                     "1월 2일 오후 2시 이전 일정 알려줘")
    assert edit_intent.ask_on_range_anchor(got) is got


# ── 좁힌 조건(Codex fix5 q2) — 한 일정 시간 변경(scope=item)에서 기준 시각이 범위 경계일 때만. 다른 경로는 그대로 ──
@pytest.mark.parametrize("raw,expected", [
    ({"anchor_kind": "time", "relation": "before", "anchor_time": "14:00"}, True),
    ({"anchor_kind": "time", "relation": "after", "anchor_time": "09:30"}, True),
    ({"anchor_kind": "time", "relation": "at", "anchor_time": "14:00"}, False),       # 새 시작
    ({"anchor_kind": "time", "relation": "before", "anchor_time": ""}, False),         # 시각 없음
    ({"anchor_kind": "time", "relation": "before", "anchor_time": "25:00"}, False),    # 잘못된 시각
    ({"anchor_kind": "item", "relation": "before", "anchor_time": "14:00"}, False),    # 기준이 일정
    ({"anchor_kind": "now", "relation": "after", "anchor_time": ""}, False),
    ({"anchor_kind": "none", "relation": "at", "anchor_time": ""}, False),
])
def test_range_boundary_reads_only_the_structured_fields(raw, expected):
    assert edit_intent.range_boundary(raw) is expected


def test_following_after_an_anchor_stop_is_not_touched():
    message = "인사동 뒤 일정 전부 30분 미뤄줘"
    raw = t04_raw(anchor_kind="item", anchor_item="i2", anchor_time="", relation="after", minutes=30, condition_text="",
                  time_edit={"time": "", "scope": "following", "cascade": False, "boundary": "shift", "evidence": message,
                             "duration_minutes": 0, "continue_previous": False})
    _, got = decided(raw, message)
    assert edit_intent.ask_on_range_anchor(got) is got


def test_following_scope_with_a_time_anchor_is_left_to_its_own_path():
    """following 은 기준 일정 경로다 — 이 검사는 한 일정(scope=item)만 본다(좁힌 조건)."""
    _, got = decided(t04_raw(time_edit={"time": "", "scope": "following", "cascade": False, "boundary": "shift",
                                        "evidence": T04, "duration_minutes": 0, "continue_previous": False}, minutes=-60))
    assert edit_intent.range_anchor_conflict(got) is None


def test_place_actions_and_add_item_are_not_touched():
    for over in ({"action": "apply_change", "time_edit": {**t04_raw()["time_edit"], "boundary": "none", "evidence": ""}},
                 {"action": "add_item", "destination_text": "카페", "target_item": "none", "choices": [],
                  "time_edit": {**t04_raw()["time_edit"], "boundary": "none", "evidence": ""}}):
        decision = SimpleNamespace(action=over["action"], item=None, raw=t04_raw(**over))
        assert edit_intent.range_anchor_conflict(decision) is None


def test_moving_a_stop_to_now_still_works_after_the_defense():
    message = "인사동 지금 갈래"
    items, got = decided(t04_raw(anchor_kind="now", anchor_time="", relation="at", condition_text="",
                                 time_edit={**t04_raw()["time_edit"], "evidence": message, "cascade": False}), message)
    assert edit_intent.ask_on_range_anchor(got) is got
    ops, _ = chat_edit.ops_for(got, items=items, now=NOW, message=message)
    assert [op.starts_at for op in ops] == ["09:00"]
