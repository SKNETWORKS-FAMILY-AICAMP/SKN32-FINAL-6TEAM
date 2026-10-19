# -*- coding: utf-8 -*-
"""일정 안내에 얹는 캐치테이블 시험 값 한 줄 — `[2026-10-19 사용자 지시]`.

새 알림을 만들지 않고 ② 다음 일정 · ③ 출발 안내에 「참고 · 하동관 웨이팅 41팀 (12:03 확인 · 제휴 전제 시험)」 한 줄만 붙는다.
말은 틀에, 수 · 시각 · 이름은 값에 둔다(언어마다 틀만 옮긴다). 읽기가 실패해도 안내는 그대로 간다.
계획: `wiki/records/plans/2026-10-16_catchtable_trial_live_card.md`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch import trip_reminders as notices
from app.infrastructure.notify.phrase import Phrase, slot_counts

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 20, 11, 50, tzinfo=KST)
READ = "2026-10-20T11:43:00+09:00"


def item(seq, kind, title, start_min, end_min=None):
    start = datetime(2026, 10, 20, 11, 0, tzinfo=KST) + timedelta(minutes=start_min)
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=None, starts_at=start,
                ends_at=start + timedelta(minutes=end_min) if end_min else None)


def test_line_says_the_waiting_and_tables_with_the_read_time():
    got = notices.with_trial_live(Phrase("{leave} 출발.", {"leave": "12:10"}), "하동관",
                                  [{"topic": "waiting", "state": "yes", "num": 41, "asked_at": READ},
                                   {"topic": "vacancy", "state": "no", "num": None, "asked_at": "2026-10-20T11:40:00+09:00"}])
    assert got.render() == "12:10 출발.\n참고 · 하동관 웨이팅 41팀 · 예약 가능한 시간 없음 (11:43 확인 · 제휴 전제 시험)"


def test_numbers_time_and_name_are_values_not_words_of_the_template():
    got = notices.with_trial_live(Phrase("출발."), "하동관", [{"topic": "waiting", "state": "yes", "num": 41, "asked_at": READ}])
    assert "41" not in got.template and "하동관" not in got.template and "11:43" not in got.template
    assert slot_counts(got.template) == {"trial_place": 1, "trial_waiting": 1, "trial_at": 1}


@pytest.mark.parametrize("rows", [None, [], [{"topic": "waiting", "state": "unknown", "asked_at": READ}],
                                  [{"topic": "hours", "state": "yes", "asked_at": READ}],
                                  [{"topic": "waiting", "state": "yes", "num": 4, "asked_at": "모름"}],
                                  [{"topic": "waiting", "state": "yes", "num": 4, "asked_at": "2026-10-20T11:43:00"}]])
def test_nothing_sayable_leaves_the_notice_as_it_was(rows):
    phrase = Phrase("출발.", {"a": 1})
    assert notices.with_trial_live(phrase, "하동관", rows) is phrase


def test_waiting_without_a_count_or_no_waiting_is_said_in_words():
    got = notices.with_trial_live(Phrase("출발."), "하동관", [{"topic": "waiting", "state": "yes", "num": None, "asked_at": READ}])
    assert got.render().endswith("하동관 웨이팅 있음 (11:43 확인 · 제휴 전제 시험)")
    got = notices.with_trial_live(Phrase("출발."), "하동관", [{"topic": "waiting", "state": "no", "asked_at": READ}])
    assert got.render().endswith("하동관 웨이팅 없음 (11:43 확인 · 제휴 전제 시험)")


def _runner(trial_live):
    return notices.TripReminders(store=None, connection_factory=None, clock=lambda: NOW, rules=notices.ReminderRules(),
                                 trial_live=trial_live)


def _reminders(items, at):
    return {r.kind: r for r in notices.plan_reminders(items, now=at, rules=notices.ReminderRules())}


@pytest.fixture
def day():
    # 11:00 경복궁(~11:50) → 11:50 이동(~12:10) → 12:10 하동관
    return [item(1, "activity", "경복궁", 0, 50), item(2, "mobility", "경복궁 → 하동관", 50, 20), item(3, "dining", "하동관", 70, 60)]


def test_departure_notice_to_a_restaurant_carries_the_line(day):
    seen = []
    runner = _runner(lambda target, now: seen.append((target.title, now)) or
                     [{"topic": "waiting", "state": "yes", "num": 41, "asked_at": READ}])
    payload = runner._payload(uuid4(), {"version": 1}, day, _reminders(day, NOW)["departure"], NOW, notices.ReminderTickResult())
    assert payload["text"].endswith("참고 · 하동관 웨이팅 41팀 (11:43 확인 · 제휴 전제 시험)")
    assert payload["values"]["trial_waiting"] == 41 and seen == [("하동관", NOW)]


def test_next_item_notice_to_a_restaurant_carries_the_line(day):
    at = day[0].starts_at
    runner = _runner(lambda target, now: [{"topic": "vacancy", "state": "yes", "asked_at": READ}])
    payload = runner._payload(uuid4(), {"version": 1}, day, _reminders(day, at)["next_item"], at, notices.ReminderTickResult())
    assert "다음 일정: 12:10 하동관." in payload["text"]
    assert payload["text"].endswith("참고 · 하동관 예약 가능한 시간 있음 (11:43 확인 · 제휴 전제 시험)")


def test_notice_to_an_activity_is_not_touched():
    items = [item(1, "dining", "하동관", 0, 50), item(2, "mobility", "하동관 → 경복궁", 50, 20), item(3, "activity", "경복궁", 70, 60)]
    called = []
    runner = _runner(lambda target, now: called.append(target) or [])
    payload = runner._payload(uuid4(), {"version": 1}, items, _reminders(items, NOW)["departure"], NOW, notices.ReminderTickResult())
    assert "참고" not in payload["text"] and called == []


def test_without_the_reader_or_with_no_value_the_notice_is_unchanged(day):
    reminder = _reminders(day, NOW)["departure"]
    plain = _runner(None)._payload(uuid4(), {"version": 1}, day, reminder, NOW, notices.ReminderTickResult())
    empty = _runner(lambda target, now: [])._payload(uuid4(), {"version": 1}, day, reminder, NOW, notices.ReminderTickResult())
    assert "참고" not in plain["text"] and plain["text"] == empty["text"] and plain["template"] == empty["template"]


def test_a_failing_read_does_not_stop_the_notice(day, caplog):
    def broken(target, now):
        raise RuntimeError("db down")

    payload = _runner(broken)._payload(uuid4(), {"version": 1}, day, _reminders(day, NOW)["departure"], NOW,
                                       notices.ReminderTickResult())
    assert payload["text"].startswith("11:50 출발") and "참고" not in payload["text"]
    assert any(record.getMessage() == "trial_live_unavailable" for record in caplog.records)


def test_assembled_reader_follows_the_switch_and_the_meal_window(monkeypatch):
    # 조립(`composition.build_dining_trial_live`) — 스위치 · 식사 1시간 전 구간을 지나야만 원장을 읽는다
    from contextlib import nullcontext

    from app import composition
    from app.domains.travel_ops.components import settings_hook
    from app.domains.travel_ops.instances.dining import ledger

    reads = []
    monkeypatch.setattr("app.core.service_bindings.current_bindings", lambda: None)
    monkeypatch.setattr(composition, "get_connection", lambda: nullcontext("conn"))
    monkeypatch.setattr(ledger, "trial_live", lambda conn, tenant, places: reads.append((conn, tenant, places)) or [["값"]])
    switch = {"on": False}
    settings_hook.register(lambda tenant, name: switch["on"] if name == settings_hook.DINING_TRIAL_LIVE_VIEW else None)
    try:
        read = composition.build_dining_trial_live("t1")
        lunch = item(3, "dining", "하동관", 70, 60)
        lunch.place = {"place_id": "p1"}
        assert read(lunch, NOW) == [] and reads == []                       # 꺼짐
        switch["on"] = True
        assert read(lunch, lunch.starts_at - timedelta(minutes=61)) == []    # 1시간보다 이르다
        assert reads == []
        assert read(lunch, NOW) == ["값"]                                     # 켜짐 · 20분 전
        assert reads == [("conn", "t1", [{"place_id": "p1"}])]
    finally:
        settings_hook.clear()
