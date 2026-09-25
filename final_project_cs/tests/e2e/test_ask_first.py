# -*- coding: utf-8 -*-
"""일정이 꼬였을 때 **바꿀지 · 물을지 · 알리기만 할지** — 확정 시나리오로 흘린다. `[2026-09-24]` D-020

★기본(설문 15번이 없거나 「비슷한 곳으로」)은 지금까지와 같다 — `tests/e2e/test_trip_api.py` 가 본다.
  이 파일은 새로 갈린 길을 본다.

    「먼저 물어봐줘」   → 바꾸지 않고 안 1·2·3을 보관하고 묻는다. 고르면 그 안으로, 답이 없으면 그 일정이
                        끝날 때 닫고(바꾸지 않음) 다음 일정으로 간다
    「변경 안 할 일정」 → 15번 답과 상관없이 바꾸지 않고 묻는다
    안전 사건           → 「먼저 물어봐줘」면 알림만(바꾸지 않음), 아니면 최적 일정으로 바로 바꾼다

재현:

    python -m pytest tests/e2e/test_ask_first.py -v
"""
from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.pending import PendingStore, ProposalRefused, choose, decide, is_safety
from app.modules.travel_ops.survey import SURVEY_VERSION

from .test_trip_api import SCENARIO, _create, _detail, _slot, api  # noqa: F401 — 픽스처를 그대로 쓴다

ANSWER_LINE = "답이 없으면 원래 일정을 그대로 둡니다"


def _ask_first(api) -> str:
    constraints = {**SCENARIO["trip"]["constraints"],
                   "survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}}
    return _create(api, constraints=constraints)["trip_id"]


def _proposals(api, trip_id):
    with get_connection() as conn:
        return PendingStore(api["tenant"]).list(conn, trip_id)


def _choose(api, trip_id, proposal_id, key, by="web"):
    store = api["store"]
    with get_connection() as conn, conn.transaction():
        places = {str(p["place_id"]): p for p in store.places(conn)}
        return choose(conn=conn, store=store, pending=PendingStore(api["tenant"]), trip_id=trip_id,
                      proposal_id=proposal_id, key=key, by=by, places_by_id=places, check=None)


# ── 「먼저 물어봐줘」 ─────────────────────────────────────────────
def test_ask_first_does_not_change_the_day_and_asks_instead(api):
    """★기본이면 09:00 에 스카이 데크를 아쿠아리움으로 **바꿨다**. 여기서는 바꾸지 않고 묻는다."""
    trip_id = _ask_first(api)
    tick = api["tick"]("09:00")
    assert tick.adjusted == [] and len(tick.asked) == 1
    assert tick.asked[0]["reason"] == "ask_first" and tick.asked[0]["safety"] is False
    assert _detail(api, trip_id)["version"] == 1                   # 일정은 그대로

    [proposal] = _proposals(api, trip_id)
    assert proposal["status"] == "open" and proposal["options_json"][0]["rank"] == 1
    assert proposal["options_json"][0]["name"] == "아쿠아리움"      # 1위는 바꿨을 때와 같은 안
    notice = api["notices"]()[-1][1]
    assert notice["type"] == "proposal_request" and ANSWER_LINE in notice["text"]
    assert [o["rank"] for o in notice["options"]] == list(range(1, len(notice["options"]) + 1))


def test_the_watcher_does_not_ask_the_same_thing_every_three_minutes(api):
    trip_id = _ask_first(api)
    api["tick"]("09:00")
    before = len(api["notices"]())
    again = api["tick"]("09:03")
    assert again.asked == [] and len(api["notices"]()) == before
    assert len(_proposals(api, trip_id)) == 1


def test_choosing_an_option_applies_it_and_closes_the_question(api):
    trip_id = _ask_first(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    first = proposal["options_json"][0]["key"]

    outcome = _choose(api, trip_id, proposal["proposal_id"], first, by="web:guest")
    assert outcome["status"] == "chosen" and outcome["version"] == 2
    assert _slot(_detail(api, trip_id), 2)["place"] == "아쿠아리움"
    [closed] = _proposals(api, trip_id)
    assert closed["status"] == "chosen" and closed["chosen_by"] == "web:guest"
    assert api["notices"]()[-1][1]["type"] == "change_notice"

    # ★일행이 동시에 눌렀다 — 먼저 닫은 쪽이 이긴다. 나중 쪽은 바꾸지 못한다
    with pytest.raises(ProposalRefused) as late:
        _choose(api, trip_id, proposal["proposal_id"], first)
    assert late.value.code == "already_decided"
    assert _detail(api, trip_id)["version"] == 2


def test_keeping_the_original_changes_nothing(api):
    trip_id = _ask_first(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    assert _choose(api, trip_id, proposal["proposal_id"], None) == {"status": "kept"}
    assert _detail(api, trip_id)["version"] == 1
    assert _proposals(api, trip_id)[0]["status"] == "kept"


def test_no_answer_until_the_item_ends_closes_it_without_changing(api):
    """★무응답 — 그 일정(10:00~10:45)이 끝나면 닫는다. **바꾸지 않는다.** 그 뒤는 다음 일정으로 진행한다."""
    trip_id = _ask_first(api)
    api["tick"]("09:00")
    assert api["tick"]("10:30").expired == []                     # 아직 그 일정 중
    later = api["tick"]("10:46")
    assert [row["trip_id"] for row in later.expired] == [trip_id]
    assert _proposals(api, trip_id)[0]["status"] == "expired"
    assert _detail(api, trip_id)["version"] == 1                   # ★끝까지 바꾸지 않았다


def test_a_stale_choice_is_refused(api):
    """고객이 본 뒤로 일정이 바뀌었으면 고르지 못한다 — 보지 않은 일정 위에 얹지 않는다."""
    trip_id = _ask_first(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    store = api["store"]
    with get_connection() as conn, conn.transaction():
        trip, items = store.latest(conn, trip_id)
        store.append_version(conn, trip_id=trip_id, base_version=trip["version"], items=items,
                             reason="test_other_change", causes=[])
    with pytest.raises(ProposalRefused) as refused:
        _choose(api, trip_id, proposal["proposal_id"], proposal["options_json"][0]["key"])
    assert refused.value.code == "stale"


# ── 「변경 안 할 일정」 ─────────────────────────────────────────────
def test_an_item_marked_do_not_change_is_asked_about_even_by_default(api):
    """★15번이 없는(기본) 여행이라도 「변경 안 할 일정」이면 바꾸지 않고 묻는다."""
    body_items = []
    for it in SCENARIO["items"]:
        detail = dict(it.get("detail", {}))
        if it["seq"] == 2:
            detail["customer_pinned"] = True
        body_items.append({"seq": it["seq"], "kind": it["kind"], "title": it["title"],
                           "place": it.get("place"), "route": it.get("route"),
                           "starts_at": f"{SCENARIO['trip']['date']}T{it['start']}:00+09:00",
                           "ends_at": f"{SCENARIO['trip']['date']}T{it['end']}:00+09:00",
                           "detail": detail})
    trip_id = _create(api, items=body_items)["trip_id"]
    tick = api["tick"]("09:00")
    assert tick.adjusted == [] and tick.asked[0]["reason"] == "protected"
    assert _detail(api, trip_id)["version"] == 1
    assert _proposals(api, trip_id)[0]["protected_by"] == "customer_pinned"


# ── 안전 사건 (판정 부품) ─────────────────────────────────────────
def _item(**kw) -> Item:
    from datetime import datetime
    from uuid import uuid4

    base = dict(item_id=uuid4(), seq=1, kind="activity", title="한강 공원 산책", place_id=uuid4(),
                starts_at=datetime(2026, 10, 5, 10), ends_at=datetime(2026, 10, 5, 11))
    return Item(**{**base, **kw})


QUAKE = {"verdict": "disrupted", "disruptions": [{"category": "earthquake", "kind": "지진 규모 4.1"}]}
DUST = {"verdict": "disrupted", "disruptions": [{"category": "air_quality", "kind": "PM10 경보 기준 초과"}]}
ASK = {"survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}}


@pytest.mark.parametrize("report,expected", [
    (QUAKE, True),
    ({"disruptions": [{"category": "disaster_msg", "kind": "긴급재난문자"}]}, True),
    ({"disruptions": [{"category": "weather_warning", "kind": "호우경보"}]}, True),
    ({"disruptions": [{"category": "weather_warning", "kind": "호우주의보"}]}, False),   # 주의보는 아니다
    (DUST, False),
    ({"disruptions": [{"category": "traffic_control", "kind": "집회"}]}, False),
    (None, False),
])
def test_what_counts_as_a_safety_event(report, expected):
    assert is_safety(report) is expected


def test_ask_first_with_a_safety_event_only_alerts():
    """★「먼저 물어봐줘」면 안전 사건도 **알림만** — 판단은 사용자가 한다(사용자 결정 2026-09-24)."""
    decision = decide(constraints=ASK, item=_item(), report=QUAKE)
    assert (decision.action, decision.reason, decision.safety) == ("safety_alert", "safety_alert", True)


def test_default_with_a_safety_event_changes_to_the_best_plan():
    """★15번이 없거나 「비슷한 곳으로」면 안전 사건도 **최적 일정으로 바로** 바꾼다."""
    for constraints in ({}, {"survey": {"version": SURVEY_VERSION, "on_disruption": "replace"}}):
        decision = decide(constraints=constraints, item=_item(), report=QUAKE)
        assert decision.action == "apply" and decision.safety is True


def test_a_do_not_change_item_hit_by_a_safety_event_is_asked_with_a_safety_head():
    decision = decide(constraints={}, item=_item(detail={"customer_pinned": True}), report=QUAKE)
    assert (decision.action, decision.reason, decision.safety) == ("ask", "protected", True)


def test_money_alone_does_not_protect_an_item():
    """★돈이 걸렸는지(예약 연결)는 따지지 않는다 — 바꾸기 싫은 일정은 「변경 안 할 일정」으로 적는다."""
    from uuid import uuid4

    decision = decide(constraints={}, item=_item(booking_id=uuid4()), report=DUST)
    assert decision.action == "apply"
