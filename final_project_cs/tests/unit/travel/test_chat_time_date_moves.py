"""채팅 시각·날짜 옮기기 — 절대 시각·날짜만·날짜와 시각·날짜와 체류, 되돌릴 것 없음 답(2026-10-26)."""
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du
from app.domains.travel_ops.components.conversation.chat_edit import EditRefused, ops_for
from app.domains.travel_ops.components.conversation.decision_unit import Decision, decide, stops_of
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, 0, tzinfo=KST)
DAY1 = datetime(2030, 1, 2, tzinfo=KST)


def stop(title, day=0, start=(10, 0), end=(11, 0), seq=1):
    base = DAY1 + timedelta(days=day)
    place = {"place_id": uuid4(), "name": title, "kind": "activity", "latitude": 37.57, "longitude": 126.98,
             "attributes": {"hours": ["00:00", "23:59"]}}
    return Item(item_id=uuid4(), seq=seq, kind="activity", title=title, place_id=place["place_id"], place=place,
                starts_at=base.replace(hour=start[0], minute=start[1]), ends_at=base.replace(hour=end[0], minute=end[1]))


def plan():
    return [stop("북촌한옥마을", seq=1), stop("인사동", start=(12, 0), end=(13, 0), seq=2),
            stop("N서울타워", start=(15, 0), end=(16, 30), seq=3),
            stop("국립중앙박물관", day=1, start=(10, 0), end=(11, 0), seq=4)]


def temporal(boundary="start", time="", evidence="옮겨줘", **kw):
    return {"boundary": boundary, "scope": "item", "time": time, "duration_minutes": 0, "cascade": False,
            "continue_previous": False, "evidence": evidence, **kw}


def change(target, spec, minutes=None, **raw):
    return Decision(action="change_time", item=target, change=None, fact="none", minutes=minutes, question="",
                    raw={"time_edit": spec, "anchor_kind": "none", "anchor_time": "", "at_day": "none", **raw})


# ── 절대 시각(T10 계열) ──────────────────────────────────────────────
@pytest.mark.parametrize("message", ["타워를 오후 11시 30분으로 미뤄줘", "인사동을 14시 50분으로 미뤄줘", "점심을 2시10분으로 당겨줘"])
def test_clock_minutes_are_not_a_shift_size(message):
    assert du.spoken_minutes(message) is None


def test_shift_sizes_still_counted_next_to_clocks():
    assert [du.spoken_minutes(m) for m in ("1시간 30분 미뤄줘", "30분 늦춰줘", "오후 3시 30분 이후 일정을 1시간 미뤄줘",
                                           "11시30분 일정을 20분 미뤄줘")] == [90, 30, 60, 20]


def test_absolute_clock_late_at_night_refuses_midnight_instead_of_moving_by_its_minutes():
    """「오후 11시 30분으로 미뤄줘」 — 모델이 shift 로 골라도 서버는 시각의 30분을 이동 크기로 쓰지 않는다."""
    items = plan()
    tower = items[2]
    raw = {"action": "change_time", "target_item": "i3", "target_change": "none", "fact": "none", "minutes": 2340,
           "choices": [], "destination_text": "", "condition_text": "", "anchor_kind": "none", "anchor_item": "none",
           "anchor_time": "", "at_day": "none", "relation": "at", "steps": 1,
           "time_edit": temporal("shift", evidence="오후 11시 30분으로 미뤄줘"),
           "place_search": {"relation": "none", "anchor_item": "none", "place_text": "", "evidence": ""},
           "place_setting": {"want": "any", "evidence": ""}}
    model = SimpleNamespace(structured=lambda *a, **k: dict(raw))
    message = "N서울타워를 오후 11시 30분으로 미뤄줘"
    got = decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=None, message=message, now=NOW)
    assert got.action == "change_time" and got.item.item_id == tower.item_id
    assert got.minutes is None
    with pytest.raises(EditRefused) as refused:
        ops_for(got, items=items, now=NOW, message=message)
    assert refused.value.code == "need_time"          # 모델이 시각을 구조로 내지 않으면 다시 묻는다 — 30분 이동이 아니다


@pytest.mark.parametrize("boundary", ["shift", "start"])
def test_validated_absolute_clock_crossing_midnight_is_refused_clearly(boundary):
    items = plan()
    got = change(items[2], temporal(boundary, time="23:30", evidence="오후 11시 30분으로"), minutes=30)
    with pytest.raises(EditRefused) as refused:
        ops_for(got, items=items, now=NOW, message="N서울타워를 오후 11시 30분으로 미뤄줘")
    assert refused.value.code == "crosses_midnight" and "자정" in refused.value.message


def test_shift_with_validated_clock_moves_to_that_clock_keeping_stay():
    items = plan()
    ops, _ = ops_for(change(items[1], temporal("shift", time="14:10", evidence="2시 10분으로"), minutes=10),
                     items=items, now=NOW)
    assert [(o.date, o.starts_at, o.ends_at) for o in ops] == [("2030-01-02", "14:10", "15:10")]


# ── 날짜 옮기기 ──────────────────────────────────────────────────────
def test_day_only_move_keeps_clock_and_stay():
    items = plan()
    ops, _ = ops_for(change(items[2], temporal("start", evidence="다음 날로 옮겨줘"), at_day="d2"), items=items, now=NOW)
    assert [(o.item_id, o.date, o.starts_at, o.ends_at) for o in ops] == [(items[2].item_id, "2030-01-03", "15:00", "16:30")]


def test_day_and_clock_move_together():
    items = plan()
    ops, _ = ops_for(change(items[0], temporal("start", time="10:00", evidence="1월 3일 오전 10시로"), at_day="d2"),
                     items=items, now=NOW)
    assert [(o.date, o.starts_at, o.ends_at) for o in ops] == [("2030-01-03", "10:00", "11:00")]


def test_day_with_only_legacy_start_clock_uses_that_clock():
    """실 E4B D02(2026-10-26): start·time="" 에 구형 anchor_time=13:00·at_day=d2 — 날만 옮기면 같은 날 일정과 겹쳐 거절됐다. 구형 시작 시각을 쓴다."""
    items = plan()
    got = change(items[0], temporal("start", evidence="1월 3일 오후 1시로 옮겨줘"), at_day="d2",
                 anchor_kind="time", anchor_time="13:00")
    ops, _ = ops_for(got, items=items, now=NOW, message="북촌한옥마을을 1월 3일 오후 1시로 옮겨줘")
    assert [(o.date, o.starts_at, o.ends_at) for o in ops] == [("2030-01-03", "13:00", "14:00")]


def test_legacy_day_only_move_without_time_edit_still_moves():
    items = plan()
    got = change(items[2], temporal("none", evidence=""), at_day="d2")
    ops, _ = ops_for(got, items=items, now=NOW)
    assert [(o.date, o.starts_at, o.ends_at) for o in ops] == [("2030-01-03", "15:00", "16:30")]


def test_start_without_clock_on_same_day_still_asks():
    items = plan()
    with pytest.raises(EditRefused) as refused:
        ops_for(change(items[2], temporal("start")), items=items, now=NOW)
    assert refused.value.code == "need_time"
    with pytest.raises(EditRefused) as same_day:
        ops_for(change(items[2], temporal("start"), at_day="d1"), items=items, now=NOW)
    assert same_day.value.code == "need_time"


def test_day_only_move_outside_trip_is_refused():
    items = plan()
    with pytest.raises(EditRefused) as refused:
        # 오늘이 여행 일주일 전이면 「내일」은 여행 밖 날이다
        ops_for(change(items[2], temporal("start"), at_day="tomorrow"), items=items, now=NOW - timedelta(days=7))
    assert refused.value.code == "day_outside_trip"


def test_recorded_next_day_read_as_tomorrow_is_refused_not_silently_kept():
    """실 E4B D01(2026-10-26): 「다음 날로」를 shift·time=""·at_day=tomorrow 로 읽었다 — 여행 밖 날이면 바꾸지 않고 그 이유를 답한다."""
    items = plan()
    with pytest.raises(EditRefused) as refused:
        ops_for(change(items[2], temporal("shift", evidence="N서울타워를 다음 날로 옮겨줘"), at_day="tomorrow"),
                items=items, now=NOW - timedelta(days=7), message="N서울타워를 다음 날로 옮겨줘")
    assert refused.value.code == "day_outside_trip"


def test_day_move_into_the_past_is_refused():
    items = plan()
    later = NOW.replace(year=2030, month=1, day=3, hour=12)
    moved = [replace(i, starts_at=i.starts_at + timedelta(days=1), ends_at=i.ends_at + timedelta(days=1)) if i.seq == 4 else i
             for i in items]
    with pytest.raises(EditRefused):
        ops_for(change(moved[3], temporal("start", time="10:00", evidence="오전 10시로"), at_day="d2"), items=moved, now=later)


# ── 날짜와 머무는 시간을 함께 ────────────────────────────────────────
def test_duration_on_another_day_moves_date_and_sets_stay():
    items = plan()
    spec = temporal("duration", evidence="1월 3일에 2시간", duration_minutes=120)
    ops, _ = ops_for(change(items[0], spec, at_day="d2"), items=items, now=NOW)
    assert [(o.date, o.starts_at, o.ends_at) for o in ops] == [("2030-01-03", "10:00", "12:00")]


def test_end_on_another_day_keeps_start_clock_on_that_day():
    items = plan()
    spec = temporal("end", time="13:00", evidence="1월 3일 오후 1시까지")
    ops, _ = ops_for(change(items[0], spec, at_day="d2"), items=items, now=NOW)
    assert [(o.date, o.starts_at, o.ends_at) for o in ops] == [("2030-01-03", "10:00", "13:00")]


def test_reflow_on_another_day_stays_refused():
    items = plan()
    spec = {**temporal("reflow", evidence="다음 날 뒤 일정 맞춰줘"), "scope": "following"}
    with pytest.raises(EditRefused) as refused:
        ops_for(change(None, spec, at_day="d2", anchor_item="i1"), items=items, now=NOW)
    assert refused.value.code == "combined_date_boundary"


def test_end_on_another_day_crossing_midnight_is_refused():
    items = plan()
    spec = temporal("end", time="09:00", evidence="1월 3일 오전 9시까지")
    with pytest.raises(EditRefused):
        ops_for(change(items[2], spec, at_day="d2"), items=items, now=NOW)


# ── 되돌릴 것 없음(T15 계열) ─────────────────────────────────────────
def test_nothing_to_undo_is_a_finished_answer_not_an_input_wait():
    from app.domains.travel_ops.components.conversation.trip_messages import NothingToUndo, _undo_outcome

    assert _undo_outcome(NothingToUndo("되돌릴 변경이 없어요"))["status"] == "answered"
    assert _undo_outcome(NothingToUndo("되돌릴 변경이 없어요"))["reason"] == "nothing_to_undo"
    assert _undo_outcome("그래도 되돌릴까요?") == {"status": "ask_rollback", "text": "그래도 되돌릴까요?"}


def test_rollback_target_marks_first_version_as_nothing_to_undo(monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    store = SimpleNamespace(versions=lambda conn, trip_id: [{"version": 1}])
    monkeypatch.setattr(trip_messages, "get_connection", lambda: Conn())
    version, said = trip_messages._rollback_target(store, uuid4(), plan(), "승인하지 않을게", None, NOW, use_rules=False)
    assert version is None and isinstance(said, trip_messages.NothingToUndo) and "일정은 바꾸지 않았어요" in said
