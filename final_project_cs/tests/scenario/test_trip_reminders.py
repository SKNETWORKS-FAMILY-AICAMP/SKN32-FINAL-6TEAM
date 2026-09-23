# -*- coding: utf-8 -*-
"""일정 안내(v11 §6-B ②·③) — 운영 되잡기 작업이 때가 된 안내를 **한 번씩** 바깥함에 넣는다.

★확정 시나리오 하루(`seoul_day_taiwan_friends.json`)를 그대로 쓴다. 경로 사건은 재생이다.
"""
from __future__ import annotations

from datetime import timedelta

from app.infrastructure.db.session import get_connection
from app.infrastructure.notify.discord import render
from app.modules.travel_ops.trip_reminders import ReminderRules, TripReminders, plan_reminders

from .test_case_version_day import SCENARIO, Clock, _at, _seed, _sources
from app.modules.travel_ops.case_engine import cleanup_tenant

import pytest

RULES = ReminderRules(day_start_lead=timedelta(minutes=60), departure_lead=timedelta(minutes=15), eve_hour=20)


class _NoEvents:
    def affecting(self, targets):
        return {}


class _Broken:
    def affecting(self, targets):
        return None


@pytest.fixture()
def world():
    tenant = "remind_" + __import__("uuid").uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("07:00"))
    yield {"tenant": tenant, "store": store, "trip_id": trip_id, "clock": clock}
    cleanup_tenant(tenant)


def _reminders(world, route_events=None, **kw):
    return TripReminders(store=world["store"], connection_factory=get_connection, clock=world["clock"],
                         route_events=route_events, rules=RULES,
                         link=lambda trip_id: f"https://plan.example/{trip_id}", **kw)


def _notices(world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice' "
                    "ORDER BY available_at, dedupe_key", (world["tenant"],))
        return [(key.split(":", 1)[1], payload) for key, payload in cur.fetchall()]


def _items(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])[1]


# ── 계산 ───────────────────────────────────────────────────────
def test_windows_follow_the_first_item_and_each_move():
    """순수 계산 — 첫 항목 09:00, 이동 10:50·15:00·17:15·19:20."""
    from app.modules.travel_ops.itinerary import Item
    from uuid import uuid4

    items = [Item(item_id=uuid4(), seq=it["seq"], kind=it["kind"], title=it["title"], place_id=None,
                  starts_at=_at(it["start"]), ends_at=_at(it["end"]), detail={}) for it in SCENARIO["items"]]
    kinds = lambda hhmm: sorted(r.kind for r in plan_reminders(items, now=_at(hhmm), rules=RULES))  # noqa: E731
    assert kinds("07:59") == ["day_eve"]              # 전날 20:00 부터 하루 시작 안내 전까지
    assert kinds("08:00") == ["day_start"]
    assert kinds("09:00") == []                        # 첫 항목이 시작했다 — 늦은 아침 안내는 안 보낸다
    assert kinds("10:35") == ["departure"]
    assert kinds("10:50") == []                        # 이동이 시작했다
    moves = [r.move.seq for hhmm in ("10:40", "14:50", "17:05", "19:10")
             for r in plan_reminders(items, now=_at(hhmm), rules=RULES)]
    assert moves == [3, 6, 8, 10]


# ── 하루 전체 ──────────────────────────────────────────────────
def test_a_day_of_ticks_sends_each_reminder_once(world):
    reminders = _reminders(world, route_events=_NoEvents())
    sent = []
    for hhmm in ("07:00", "08:05", "08:30", "10:40", "10:45", "14:50", "17:05", "19:10", "21:00"):
        world["clock"].now = _at(hhmm)
        outcome = reminders.tick()
        assert outcome.fatal == [] and outcome.held == [], (hhmm, outcome)
        sent += [s["key"].split(":")[0] for s in outcome.sent]
    assert sent == ["day_eve", "day_start", "departure", "departure", "departure", "departure"]

    notices = _notices(world)
    assert len(notices) == 6 and len({key for key, _ in notices}) == 6        # ★DoD-26 — 한 번씩
    departure = next(p for k, p in notices if k.startswith("departure:"))
    assert "10:50 출발" in departure["text"] and "다음 일정: 11:15" in departure["text"]
    assert "가는 방법: 2호선 잠실→성수 직통 · 약 13분 (경로 확인 10:40)" in departure["text"]
    rendered = render(departure)
    assert rendered.endswith(f"https://plan.example/{world['trip_id']}")     # 링크는 늘 붙는다
    day = next(p for k, p in notices if k.startswith("day_start:"))
    assert day["text"].startswith("좋은 아침") and "09:00" in day["text"] and day["locale"] == "zh-TW"


def test_the_same_moment_twice_is_already_sent(world):
    world["clock"].now = _at("10:40")
    first = _reminders(world, route_events=_NoEvents()).tick()
    again = _reminders(world, route_events=_NoEvents()).tick()
    assert len(first.sent) == 1 and again.sent == [] and again.already == 1
    assert len(_notices(world)) == 1


def test_a_route_that_cannot_be_read_is_not_announced(world):
    """★결정 15 — 경로 사건을 못 읽었으면 「그럴듯한 경로 문장」을 보내지 않고 치명으로 센다."""
    world["clock"].now = _at("10:40")
    outcome = _reminders(world, route_events=_Broken()).tick()
    assert outcome.sent == [] and len(outcome.fatal) == 1
    assert _notices(world) == []


def test_a_disrupted_route_is_held_for_the_watch_then_the_new_move_is_announced(world):
    """계획한 수단에 사건 — 낡은 경로를 안내하지 않는다. 감시가 이동을 바꾸면 새 항목이 안내된다."""
    clock = world["clock"]
    _, route_events = _sources(clock)                       # 재생 — 10:45 에 2호선 무정차
    clock.now = _at("10:45")
    held = _reminders(world, route_events=route_events).tick()
    assert held.sent == [] and [h["item"] for h in held.held] == [SCENARIO["items"][2]["title"]]

    from app.modules.travel_ops.trip_watch import TripWatcher

    check, _ = _sources(clock)
    watcher = TripWatcher(store=world["store"], check=check, connection_factory=get_connection, clock=clock,
                          route_events=route_events)
    assert len(watcher.tick().adjusted) == 1                 # 감시가 이동 경로를 바꿨다(v2)
    after = _reminders(world, route_events=route_events).tick()
    assert len(after.sent) == 1, after
    text = next(p for k, p in _notices(world) if k.startswith("departure:"))["text"]
    assert "가는 방법:" in text and "2호선 잠실→성수 직통" not in text


def test_without_a_route_source_where_and_when_still_go(world):
    world["clock"].now = _at("10:40")
    outcome = _reminders(world, route_events=None).tick()
    assert len(outcome.sent) == 1 and outcome.no_route == 1
    text = _notices(world)[0][1]["text"]
    assert "10:50 출발" in text and "가는 방법" not in text and "모름" not in text


# ── 변경 통지에도 링크가 붙는다 (2026-09-20) ────────────────────
def test_a_change_notice_carries_the_plan_link(world):
    """★상태의 정본은 링크다(v11 §6-A). 전에는 안내(②·③)에만 붙고 변경 통지(①)에는 없었다."""
    from app.modules.travel_ops.plan_link import plan_url
    from app.modules.travel_ops.trip_watch import TripWatcher

    clock = world["clock"]
    check, route_events = _sources(clock)
    clock.now = _at("09:00")
    watcher = TripWatcher(store=world["store"], check=check, connection_factory=get_connection, clock=clock,
                          route_events=route_events)
    assert len(watcher.tick().adjusted) == 1
    key, payload = _notices(world)[0]
    assert key == "v2" and payload["plan_url"] == plan_url(world["tenant"], world["trip_id"])
    assert render(payload).endswith(payload["plan_url"])
