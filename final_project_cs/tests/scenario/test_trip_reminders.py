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

# ★`[2026-09-24]` 전날 안내는 껐다(D-020) — 흐름은 하루 시작 → 다음 일정 → 이동의 반복이다
# ★`[2026-09-24 사용자 지시]` 이동 알림은 **이동을 시작하는 그 시각** — 앞에 붙이는 분이 없다
RULES = ReminderRules(day_start_lead=timedelta(minutes=60), eve_hour=None)


def _kinds_sent(outcome):
    return [s["key"].split(":")[0] for s in outcome.sent]


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
    assert kinds("07:59") == []                        # ★전날 안내는 껐다 — 08:00 전에는 아무것도 없다
    assert kinds("08:00") == ["day_start"]             # 하루 시작 — 팀 기본 08:00
    assert kinds("09:00") == ["next_item"]             # 첫 일정(조식)이 시작 — 다음 일정(10:00) 안내
    assert kinds("10:35") == ["next_item"]             # 10:00 일정 중 — ★이동(10:50)은 아직 알리지 않는다
    assert kinds("10:49") == []                        # ★「N분 전」 이동 알림은 없다(앞 판은 10:35 에 나갔다)
    assert kinds("10:50") == ["departure"]             # ★이동을 시작하는 그 시각
    assert kinds("11:10") == []                        # 이동이 끝났다 — 끝난 뒤의 「출발하세요」는 없다
    moves = [r.move.seq for hhmm in ("10:50", "15:00", "17:15", "19:20")
             for r in plan_reminders(items, now=_at(hhmm), rules=RULES) if r.kind == "departure"]
    assert moves == [3, 6, 8, 10]


# ── 하루 전체 ──────────────────────────────────────────────────
def test_a_day_of_ticks_sends_each_reminder_once(world):
    reminders = _reminders(world, route_events=_NoEvents())
    sent = []
    for hhmm in ("07:00", "08:05", "08:30", "10:40", "10:50", "15:00", "17:15", "19:20", "21:00"):
        world["clock"].now = _at(hhmm)
        outcome = reminders.tick()
        assert outcome.fatal == [] and outcome.held == [], (hhmm, outcome)
        sent += [s["key"].split(":")[0] for s in outcome.sent]
    # ★하루 시작 → (10:40 틱: 10:00 일정의 다음 일정 안내) → 이동(출발 시각) … 틱이 일정 시작 시각에 걸린
    #   곳에서만 「다음 일정」이 나간다. 운영의 되잡기는 1분마다 돈다.
    assert sent == ["day_start", "next_item", "departure", "departure", "departure", "departure"]

    notices = _notices(world)
    assert len(notices) == 6 and len({key for key, _ in notices}) == 6        # ★DoD-26 — 한 번씩
    departure = next(p for k, p in notices if k.startswith("departure:"))
    assert "10:50 출발" in departure["text"] and "다음 일정: 11:15" in departure["text"]
    assert "가는 방법: 2호선 잠실→성수 직통 · 약 13분 (경로 확인 10:50)" in departure["text"]
    rendered = render(departure)
    assert rendered.endswith(f"https://plan.example/{world['trip_id']}")     # 링크는 늘 붙는다
    day = next(p for k, p in notices if k.startswith("day_start:"))
    assert day["text"].startswith("좋은 아침") and "09:00" in day["text"] and day["locale"] == "zh-TW"


def test_the_same_moment_twice_is_already_sent(world):
    world["clock"].now = _at("10:50")
    first = _reminders(world, route_events=_NoEvents()).tick()
    again = _reminders(world, route_events=_NoEvents()).tick()
    assert _kinds_sent(first) == ["departure"]
    assert again.sent == [] and again.already == 1
    assert len(_notices(world)) == 1


def test_a_route_that_cannot_be_read_is_not_announced(world):
    """★결정 15 — 경로 사건을 못 읽었으면 「그럴듯한 경로 문장」을 보내지 않고 치명으로 센다."""
    world["clock"].now = _at("10:50")
    outcome = _reminders(world, route_events=_Broken()).tick()
    assert "departure" not in _kinds_sent(outcome) and len(outcome.fatal) == 1
    assert not any(k.startswith("departure:") for k, _ in _notices(world))


def test_a_disrupted_route_is_held_for_the_watch_then_the_new_move_is_announced(world):
    """계획한 수단에 사건 — 낡은 경로를 안내하지 않는다. 감시가 이동을 바꾸면 새 항목이 안내된다."""
    clock = world["clock"]
    _, route_events = _sources(clock)                       # 재생 — 10:45 에 2호선 무정차
    clock.now = _at("10:50")
    held = _reminders(world, route_events=route_events).tick()
    assert "departure" not in _kinds_sent(held)
    assert [h["item"] for h in held.held] == [SCENARIO["items"][2]["title"]]

    from app.modules.travel_ops.trip_watch import TripWatcher

    check, _ = _sources(clock)
    watcher = TripWatcher(store=world["store"], check=check, connection_factory=get_connection, clock=clock,
                          route_events=route_events)
    assert len(watcher.tick().adjusted) == 1                 # 감시가 이동 경로를 바꿨다(v2)
    after = _reminders(world, route_events=route_events).tick()
    assert _kinds_sent(after) == ["departure"], after
    text = next(p for k, p in _notices(world) if k.startswith("departure:"))["text"]
    assert "가는 방법:" in text and "2호선 잠실→성수 직통" not in text


def test_without_a_route_source_where_and_when_still_go(world):
    world["clock"].now = _at("10:50")
    outcome = _reminders(world, route_events=None).tick()
    assert "departure" in _kinds_sent(outcome) and outcome.no_route == 1
    text = next(p for k, p in _notices(world) if k.startswith("departure:"))["text"]
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


# ── 새 흐름 (2026-09-24, D-020) ────────────────────────────────
def test_the_next_item_notice_says_what_is_next_and_when_to_leave(world):
    """② 조식(09:00)이 시작할 때 — 다음 일정(10:00 스카이 데크). 사이에 이동이 없으면 출발 줄도 없다."""
    world["clock"].now = _at("09:00")
    outcome = _reminders(world, route_events=_NoEvents()).tick()
    assert _kinds_sent(outcome) == ["next_item"]
    payload = _notices(world)[0][1]
    assert payload["type"] == "guidance" and payload["kind"] == "next_item"
    assert payload["text"].startswith("지금 일정:") and "다음 일정: 10:00" in payload["text"]
    assert "출발 예정" not in payload["text"]

    # 10:00 일정 → 다음(11:15) 사이에 10:50 이동이 끼어 있다 — 몇 시에 나서는지 미리 알린다
    world["clock"].now = _at("10:00")
    _reminders(world, route_events=_NoEvents()).tick()
    text = next(p for k, p in _notices(world) if k.startswith("next_item:") and "11:15" in p["text"])["text"]
    assert "10:50 출발 예정" in text


def test_the_day_starts_at_eight_unless_the_first_item_is_earlier():
    """★하루 시작은 사용자 설정이 없으면 08:00. 첫 일정이 그보다 이르면 그 전으로 당긴다."""
    from uuid import uuid4

    from app.modules.travel_ops.itinerary import Item

    late = [Item(item_id=uuid4(), seq=1, kind="activity", title="늦은 시작", place_id=None,
                 starts_at=_at("11:00"), ends_at=_at("12:00"), detail={})]
    assert [r.due_at for r in plan_reminders(late, now=_at("08:00"), rules=RULES)] == [_at("08:00")]
    assert plan_reminders(late, now=_at("07:59"), rules=RULES) == []

    early = [Item(item_id=uuid4(), seq=1, kind="activity", title="이른 시작", place_id=None,
                  starts_at=_at("07:30"), ends_at=_at("08:30"), detail={})]
    [start] = [r for r in plan_reminders(early, now=_at("06:30"), rules=RULES) if r.kind == "day_start"]
    assert start.due_at == _at("06:30")                         # 07:30 − 60분


def test_a_day_start_the_user_set_wins():
    from uuid import uuid4

    from app.modules.travel_ops.itinerary import Item

    items = [Item(item_id=uuid4(), seq=1, kind="activity", title="오전 일정", place_id=None,
                  starts_at=_at("11:00"), ends_at=_at("12:00"), detail={})]
    day = _at("11:00").date()
    reminders = plan_reminders(items, now=_at("09:30"), rules=RULES, day_starts={day: _at("09:30")})
    assert [r.kind for r in reminders] == ["day_start"]
    assert plan_reminders(items, now=_at("08:00"), rules=RULES, day_starts={day: _at("09:30")}) == []


def test_no_departure_is_announced_toward_an_item_waiting_for_an_answer(world):
    """★답을 기다리는 일정으로 「출발하세요」를 보내지 않는다 — 대신 「답을 기다리는 중」(D-020)."""
    from app.modules.travel_ops.itinerary import Item
    from app.modules.travel_ops.pending import Decision, PendingStore

    items = _items(world)
    target = next(i for i in items if i.seq == 4)                # 10:50 이동이 향하는 11:15 일정
    with get_connection() as conn, conn.transaction():
        PendingStore(world["tenant"]).open(
            conn, trip_id=world["trip_id"], item=target, base_version=1,
            decision=Decision("ask", "ask_first", None, False), causes=[], options=[])
    world["clock"].now = _at("10:50")
    _reminders(world, route_events=_NoEvents()).tick()
    departure = next(p for k, p in _notices(world) if k.startswith("departure:"))
    assert departure.get("waiting") is True
    assert "답을 기다리고 있는 일정" in departure["text"] and "출발 —" not in departure["text"]
    assert "답이 없으면 원래 일정대로 진행합니다" in departure["text"]
    assert isinstance(target, Item)



def test_the_day_start_carries_what_changed_overnight_and_what_waits(world):
    """★새벽 3시까지 모인 이슈를 하루 시작에서 한 번에 — 바뀐 일정 수 · 답을 기다리는 일정(D-020)."""
    from app.modules.travel_ops.pending import Decision, PendingStore

    store, trip_id = world["store"], world["trip_id"]
    with get_connection() as conn, conn.transaction():
        trip, items = store.latest(conn, trip_id)
        version = store.append_version(conn, trip_id=trip_id, base_version=trip["version"], items=items,
                                       reason="auto_adjusted", causes=[])
        with conn.cursor() as cur:                          # 전날 밤에 바뀐 것으로 둔다
            cur.execute("UPDATE itinerary_versions SET created_at=%s WHERE trip_id=%s AND version=%s",
                        (_at("08:00") - timedelta(hours=6), trip_id, version))
        target = next(i for i in store.latest(conn, trip_id)[1] if i.seq == 4)
        PendingStore(world["tenant"]).open(conn, trip_id=trip_id, item=target, base_version=version,
                                           decision=Decision("ask", "ask_first", None, False),
                                           causes=[], options=[])
    world["clock"].now = _at("08:00")
    _reminders(world, route_events=_NoEvents()).tick()
    day = next(p for k, p in _notices(world) if k.startswith("day_start:"))
    assert "어제 이후 바뀐 일정이 1건" in day["text"]
    assert f"답을 기다리는 일정: {target.title}" in day["text"]
