# -*- coding: utf-8 -*-
"""Case 버전의 일정 적용기(`itinerary.apply`)도 **같은 판정 문**을 지난다. `[2026-09-25]` D-020

★시나리오용 여행 버전의 감시·신고와 같은 판정(`pending.decide`) · 같은 보류 제안 · 같은 알림이다.
★고객이 직접 고른 변경(다른 안으로 · 되돌리기)은 판정을 지나지 않는다.

재현:

    python -m pytest tests/scenario/test_case_path_gate.py -v
"""
from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.modules.travel_ops.itinerary_actions import ItineraryApply, change_arguments
from app.modules.travel_ops.itinerary_changes import ItineraryChange
from app.modules.travel_ops.survey import SURVEY_VERSION

from .test_case_version_day import _seed


@pytest.fixture()
def world():
    tenant = "gate_" + uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    yield {"tenant": tenant, "store": store, "customer": customer, "trip_id": trip_id}
    cleanup_tenant(tenant)


def _set_constraints(world, extra: dict) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trips SET constraints = constraints || %s::jsonb WHERE tenant_id=%s AND trip_id=%s",
                    (json.dumps(extra), world["tenant"], world["trip_id"]))


def _pin(world, seq: int) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE itinerary_items SET detail = detail || '{\"customer_pinned\": true}'::jsonb "
                    "WHERE tenant_id=%s AND trip_id=%s AND seq=%s", (world["tenant"], world["trip_id"], seq))


def _arguments(world, *, reason="auto_adjusted", causes=None):
    """seq 2(활동)를 다른 실재 장소로 바꾸는 변경 — 적용기가 받는 모양 그대로."""
    with get_connection() as conn:
        trip, items = world["store"].latest(conn, world["trip_id"])
        places = world["store"].places(conn)
    target = next(i for i in items if i.seq == 2)
    other = next(p for p in places if p["kind"] == "activity" and p["place_id"] != target.place_id)
    new = replace(target, item_id=uuid4(), place_id=other["place_id"], title=other["name"],
                  replaces_item_id=target.item_id, place=None)
    change = ItineraryChange(reason=reason, causes=causes or [{"category": "weather", "kind": "강수"}],
                             notice={"text": "바꿨어요", "language": "ko"},
                             replacements={target.item_id: new})
    return change_arguments(trip_id=world["trip_id"], base_version=trip["version"], change=change)


def _apply(world, arguments):
    with get_connection() as conn, conn.transaction():
        return ItineraryApply().apply(conn, tenant_id=world["tenant"], customer_id=world["customer"],
                                      case_id=uuid4(), arguments=arguments)


def _version(world) -> int:
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])[0]["version"]


def test_by_default_the_case_path_changes_the_plan(world):
    applied = _apply(world, _arguments(world))
    assert applied.summary["version"] == 2 and _version(world) == 2
    assert applied.outbox[0].dedupe_key == f"{world['trip_id']}:v2"


def test_ask_first_opens_a_proposal_instead_of_a_new_version(world):
    _set_constraints(world, {"survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}})
    arguments = _arguments(world)
    asked = _apply(world, arguments)
    assert asked.summary["status"] == "asked" and asked.summary["reason"] == "ask_first"
    assert _version(world) == 1                                          # ★바꾸지 않았다
    [message] = asked.outbox
    assert message.dedupe_key == f"{world['trip_id']}:proposal:{asked.summary['proposal_id']}"
    assert message.payload["type"] == "proposal_request" and message.payload["plan_url"]
    assert "답이 없으면 원래 일정을 그대로 둡니다" in message.payload["text"]
    again = _apply(world, arguments)                                     # 같은 변경이 또 와도 제안은 하나
    assert again.summary["already"] is True and again.outbox == []
    assert again.summary["proposal_id"] == asked.summary["proposal_id"]


def test_ask_first_with_a_safety_event_sends_a_safety_alert_and_changes_nothing(world):
    _set_constraints(world, {"survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}})
    asked = _apply(world, _arguments(world, causes=[{"category": "earthquake", "kind": "지진"}]))
    assert asked.summary["safety"] is True and asked.outbox[0].payload["type"] == "safety_alert"
    assert _version(world) == 1


def test_a_pinned_item_is_asked_about_even_without_ask_first(world):
    _pin(world, 2)
    asked = _apply(world, _arguments(world))
    assert asked.summary["status"] == "asked" and asked.summary["protected_by"] == "customer_pinned"
    assert _version(world) == 1


def test_a_change_the_customer_chose_is_not_gated(world):
    """★다른 안으로 바꿔 달라는 것은 고객의 답이다 — 「먼저 물어봐줘」여도 다시 묻지 않는다."""
    _set_constraints(world, {"survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}})
    applied = _apply(world, _arguments(world, reason="customer_request",
                                       causes=[{"category": "customer_request", "type": "alternate"}]))
    assert applied.summary["version"] == 2 and _version(world) == 2
