# -*- coding: utf-8 -*-
"""`[2026-10-27 LB-05 · TeamFlow ST4F-709]` 고를 때 다시 본 1박 값이 고객이 말한 상한을 넘으면 바꾸지 않는다.

「1박 ○원 이하」 조건으로 낸 후보(`price_limit` — 숙소 팀 206f151f)를 고를 때 재확인 값(`price_check.now`)이 그 상한을 넘으면,
웹 고르기(`trip_api._choose`)는 409 `over_price_limit` 로 거절하고 채팅 고르기(숙소 팀 `_choose`)는 일정을 그대로 둔 채 알린다.
전에는 새 가격으로 그대로 적용했다(`pending.choose`).
"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.booking.offers import recheck as recheck_module
from app.domains.travel_ops.components.booking.offers.recheck import over_price_limit, price_limit_refusal

OPTION = {"key": "myrealtrip:12", "name": "둘째 호텔", "price_per_night": 150000, "price_basis": "detail", "price_limit": 160000}
CHANGED = {"status": "changed", "before": 150000, "now": 171000, "basis": "detail"}


def test_a_recheck_above_the_said_limit_is_over_and_anything_else_is_not():
    assert over_price_limit(CHANGED, OPTION) == 160000
    assert over_price_limit({**CHANGED, "now": 160000}, OPTION) is None, "상한과 같으면 「이하」 안이다"
    assert over_price_limit(CHANGED, {**OPTION, "price_limit": None}) is None, "상한을 말하지 않았으면 비교하지 않는다"
    assert over_price_limit(CHANGED, {k: v for k, v in OPTION.items() if k != "price_limit"}) is None, "옛 후보(칸 없음)"
    assert over_price_limit({"status": "unchecked", "before": 150000, "now": None, "reason": "detail_unreadable"}, OPTION) is None, \
        "다시 보지 못했으면 넘었다고 하지 않는다(기존 「확인하지 못했어요」 안내 그대로)"
    assert over_price_limit({"status": "gone", "before": 150000, "now": None}, OPTION) is None, "객실 없음은 따로 거절한다"
    assert over_price_limit(None, OPTION) is None


def test_the_refusal_sentence_names_the_new_price_and_the_limit_and_keeps_the_plan():
    assert price_limit_refusal(CHANGED, 160000, "둘째 호텔") == (
        "둘째 호텔은(는) 다시 확인해 보니 지금 1박 171,000원이라 말씀하신 1박 160,000원 이하를 넘어요. 일정은 그대로 두었어요. "
        "다른 후보를 고르시거나 「바꿔 줘」라고 하시면 새로 찾아 드릴게요.")
    sellers = {"status": "changed", "before": 150000, "now": 171000, "basis": "sellers"}
    assert "지금 판매처 최저가 1박 171,000원~이라" in price_limit_refusal(sellers, 160000, "가까운 호텔")


# ── 채팅 고르기(숙소 팀 `_choose`) ──────────────────────────────────────────────

def _choose_with_limit(choice, detail, max_price):
    from tests.unit.travel.booking.test_lodging_team import ITEM_STATE, _held, _plan, _run, _with_conditions

    plan = _plan()
    first, _, _ = _with_conditions(plan, max_price=max_price)
    plan["items"][1]["detail"] = _held(first, plan)
    state = {**ITEM_STATE, "subject_ref": {**ITEM_STATE["subject_ref"], "request": {"type": "change", "choice": choice}}}
    return _run({"task": "unclear"}, {"read.itinerary": plan, "read.stay_detail": detail}, text="2번으로 할게",
                capability="lodging.itinerary", state=state)


def test_chat_choice_over_the_said_limit_is_not_applied():
    from tests.unit.travel.booking.test_lodging_team import DETAIL

    over, _, _ = _choose_with_limit("myrealtrip:12", {**DETAIL, "gid": 12, "price_per_night": 171000}, 160000)
    assert over.action_proposals == [], "상한을 넘는 숙소는 일정에 넣지 않는다"
    assert over.answer == ("둘째 호텔은(는) 다시 확인해 보니 지금 1박 171,000원이라 말씀하신 1박 160,000원 이하를 넘어요. "
                           "일정은 그대로 두었어요. 다른 후보를 고르시거나 「바꿔 줘」라고 하시면 새로 찾아 드릴게요.")
    assert over.decisions[0]["itinerary"] == "lodging_over_limit" and over.decisions[0]["price_limit"] == 160000
    under, _, _ = _choose_with_limit("myrealtrip:12", {**DETAIL, "gid": 12, "price_per_night": 155000}, 160000)
    new = under.action_proposals[0].arguments["replacements"][0]["item"]
    assert new["title"] == "둘째 호텔" and new["detail"]["chosen"]["price_per_night"] == 155000, "상한 안이면 새 값으로 바꾼다(기존 그대로)"


# ── 웹 고르기(`trip_api._choose`) ────────────────────────────────────────────────

TRIP = UUID("33333333-3333-3333-3333-333333333333")
PROPOSAL = UUID("44444444-4444-4444-4444-444444444444")
ITEM = UUID("55555555-5555-5555-5555-555555555555")
CUSTOMER = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def web(monkeypatch):
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.components.planning import pending
    from app.domains.travel_ops.entry import trip_api
    from app.domains.travel_ops.ports.data_sources import base as data_sources_base

    seen = {"choose": 0, "check": CHANGED}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def transaction(self):
            return nullcontext(self)

    starts = datetime(2030, 11, 6, 6, 0, tzinfo=timezone.utc)
    item = SimpleNamespace(item_id=ITEM, kind="lodging", starts_at=starts, ends_at=starts + timedelta(days=1),
                           detail={"area": "명동"}, place=None)
    trip = {"customer_id": CUSTOMER, "party_size": 2}
    proposal = {"status": "open", "reason": "requested_options", "item_id": ITEM, "options_json": [OPTION]}

    def choose(**kwargs):
        seen["choose"] += 1
        return {"status": "applied"}

    monkeypatch.setattr(trip_api, "get_connection", lambda: Conn())
    monkeypatch.setattr(TripStore, "latest", lambda self, conn, trip_id: (trip, [item]))
    monkeypatch.setattr(TripStore, "places", lambda self, conn, trip_id: [])
    monkeypatch.setattr(pending.PendingStore, "get", lambda self, conn, trip_id, proposal_id, **kw: proposal)
    monkeypatch.setattr(pending, "choose", choose)
    monkeypatch.setattr(data_sources_base, "build_travel_sources", lambda *a, **k: SimpleNamespace(travel_search=object(), stay_google=None))
    monkeypatch.setattr(recheck_module, "recheck_stay", lambda *a, **k: dict(seen["check"]))
    router = trip_api.build_trip_router()
    endpoint = next(r for r in router.routes if r.path == "/v1/web/trips/{trip_id}/proposals/{proposal_id}/choose")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[endpoint.dependant.dependencies[0].call] = lambda: ("tenant", CUSTOMER)
    return TestClient(app), seen


def test_web_choice_over_the_said_limit_is_refused_with_409_and_nothing_changes(web):
    client, seen = web
    response = client.post(f"/v1/web/trips/{TRIP}/proposals/{PROPOSAL}/choose", json={"key": "myrealtrip:12"})
    assert response.status_code == 409, response.text
    error = response.json()["detail"]["error"]
    assert error["code"] == "over_price_limit"
    assert error["message"] == ("둘째 호텔은(는) 다시 확인해 보니 지금 1박 171,000원이라 말씀하신 1박 160,000원 이하를 넘어요. "
                                "일정은 그대로 두었어요. 다른 후보를 고르시거나 「바꿔 줘」라고 하시면 새로 찾아 드릴게요.")
    assert error["detail"] == {"price_check": CHANGED, "price_limit": 160000}
    assert seen["choose"] == 0, "고르기(잠금 · 적용)를 부르지 않는다"


def test_web_choice_within_the_limit_still_applies(web):
    client, seen = web
    seen["check"] = {**CHANGED, "now": 155000}
    response = client.post(f"/v1/web/trips/{TRIP}/proposals/{PROPOSAL}/choose", json={"key": "myrealtrip:12"})
    assert response.status_code == 200, response.text
    assert seen["choose"] == 1
