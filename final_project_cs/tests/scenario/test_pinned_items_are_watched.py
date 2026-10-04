# -*- coding: utf-8 -*-
"""고객이 「바꾸지 말 것」으로 고정한 일정도 **감시한다** — 바꾸지 않고 알린다. `[2026-10-03 사용자 결정 — D-020 · 결정 8번]`

☆사용자 말: 「안 바꿔도 알림은 받게 해야 함. 바꾸지 않는 것과 알림을 끄는 것은 별개.」
☆결함: Case 버전 감시(`TripWatchCaseOpener`)가 고정(`customer_pinned`) 항목을 점검에서 **아예 빼고** 세기만 했다 — 고정한 일정에는 재난문자 · 휴무 같은 위험 알림이 안 나갔다.
  시나리오 버전(`TripWatcher`)은 이미 점검하고 묻고 있었다(코드 주석 「전에는 통째로 건너뛰어서 고정한 항목에는 안전 알림도 안 나갔다」) — 두 감시가 갈려 있었다.

★지키려는 것: ①고정한 일정도 점검해 Case 를 연다 ②**일정은 바뀌지 않는다**(자동 적용 없음 — 적용기의 「변경 안 할 일정이면 먼저 묻는다」가 막는다) ③고객은 위험 알림을 받는다
(대안이 있으면 「변경하지 않기로 한 일정이라 바꾸지 않았어요. 어떻게 할까요?」 + 안, 없으면 「일정은 그대로 두었어요」) ④안전 사건이면 안전 알림 ⑤고정이 아닌 일정은 전처럼 바로 바뀐다.

재현:

    python -m pytest tests/scenario/test_pinned_items_are_watched.py -v
"""
from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from app.infrastructure.db.session import get_connection

from .test_case_version_day import _at, case_world  # noqa: F401 — 픽스처를 그대로 쓴다

from app.modules.travel_ops.case_engine import CaseEngine
from tests.scenario.test_case_version_day import _classifier, _extractor, _sources  # noqa: F401

CLOSED = {"verdict": "disrupted", "disruptions": [{"category": "traffic_control", "kind": "road_closed"}]}
SAFETY = {"verdict": "disrupted", "disruptions": [{"category": "disaster_msg", "kind": "fire"}]}


def _items(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def _pin(world, item_id):
    """그 항목을 「변경 안 할 일정」으로 — 새 판을 하나 올린다."""
    with get_connection() as conn, conn.transaction():
        trip, items = world["store"].latest(conn, world["trip_id"])
        for item in items:
            if item.item_id == item_id:
                item.detail = {**item.detail, "customer_pinned": True}
        world["store"].append_version(conn, trip_id=world["trip_id"], base_version=trip["version"], items=items,
                                      reason="test_pin", causes=[])


def _engine(world, report, target_place_ids):
    def check(*, place, starts_at, region="서울", **_):
        return report if str(place.get("place_id")) in target_place_ids else {"verdict": "clear", "disruptions": []}

    _, route_events = _sources(world["clock"])
    return CaseEngine(tenant_id=world["tenant"], check=check, route_events=route_events, classifier=_classifier,
                      report_extractor=_extractor, clock=world["clock"])


def _notices(world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice' ORDER BY available_at",
                    (world["tenant"],))
        return [row[0] for row in cur.fetchall()]


def _proposals(world):
    from app.modules.travel_ops.pending import PendingStore

    with get_connection() as conn:
        return PendingStore(world["tenant"]).list(conn, world["trip_id"])


def _first_activity(world):
    _, items = _items(world)
    return next(i for i in items if i.kind == "activity" and i.place is not None)


# invariant: INV-CS-RT-026
def test_a_pinned_activity_is_checked_and_the_customer_is_told_but_the_itinerary_is_not_changed(case_world):
    world = case_world
    target = _first_activity(world)
    _pin(world, target.item_id)
    world["clock"].now = target.starts_at - timedelta(minutes=45)
    version_before = _items(world)[0]["version"]
    engine = _engine(world, CLOSED, {str(target.place["place_id"])})

    result = engine.tick()

    assert [row["item"] for row in result.opened] == [target.title]                  # 고정한 일정도 Case 가 열렸다(전에는 건너뛰었다)
    assert result.ran and result.ran[0]["status"] in ("resolved", "waiting_approval", "escalated")
    assert _items(world)[0]["version"] == version_before                             # ★일정은 바뀌지 않았다
    told = [n for n in _notices(world) if n.get("type") in ("proposal_request", "guidance", "safety_alert")]
    assert told, "고정한 일정에 위험이 있는데 고객에게 아무 알림도 안 나갔다"
    if _proposals(world):                                                            # 대안이 있으면 먼저 묻는다(보호 일정 → 먼저 묻기 길)
        [asked] = _proposals(world)
        assert asked["reason"] == "protected" and asked["protected_by"] == "customer_pinned" and asked["status"] == "open"
        assert any("바꾸지 않았어요" in n["text"] for n in told)
    else:                                                                            # 대안이 없으면 「그대로 두었다」 알림
        assert any(n.get("kind") == "no_alternate" and "일정은 그대로 두었어요" in n["text"] for n in told)


def test_a_pinned_item_with_a_safety_event_gets_a_safety_alert_and_is_still_not_changed(case_world):
    world = case_world
    target = _first_activity(world)
    _pin(world, target.item_id)
    world["clock"].now = target.starts_at - timedelta(minutes=45)
    version_before = _items(world)[0]["version"]

    _engine(world, SAFETY, {str(target.place["place_id"])}).tick()

    assert _items(world)[0]["version"] == version_before
    alerts = [n for n in _notices(world) if n.get("type") == "safety_alert"]
    assert alerts and all("안전" in n["text"] for n in alerts)


def test_an_unpinned_activity_with_the_same_event_is_still_changed_right_away(case_world):
    """고정은 「자동으로 바꾸지 않음」일 뿐이다 — 고정하지 않은 같은 일정은 전처럼 바로 바뀐다(알림만 받는 쪽이 늘어난 것이다)."""
    world = case_world
    target = _first_activity(world)
    world["clock"].now = target.starts_at - timedelta(minutes=45)
    version_before = _items(world)[0]["version"]

    result = _engine(world, CLOSED, {str(target.place["place_id"])}).tick()

    assert result.opened and _items(world)[0]["version"] > version_before
    assert not _proposals(world)
