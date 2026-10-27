# -*- coding: utf-8 -*-
"""`[2026-10-26 x600 a465c602]` 바꾼 뒤 답 — 다른 안을 말하고 고를 선택지를 싣는다 · 시각 되돌리기는 시각으로 말한다.

x600 증거(보고서 2026-10-26_x600_a465c602_실서버확인): 활동 「다른 곳으로」는 들고 있던 첫 안(종묘)으로 바꾸며 다른 안을 말하지 않았고,
식당 「다른 데로」는 「다른 안: 1) … 고르세요」라고 답하면서 `choices` 가 비었다. 시각만 되돌린 답은 「남산서울타워에서 남산서울타워(으)로」였다.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.conversation import case_dispatch
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import plan_rollback, plan_swap

KST = ZoneInfo("Asia/Seoul")


def spot(name):
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.58, "longitude": 126.98, "attributes": {}}


def alternate(place, note=None):
    return {"key": place["place_id"], "name": place["name"], "place_id": place["place_id"], "reason": "가까워요",
            "starts_at": None, "ends_at": None, "option": None, "option_label": None, **({"note": note} if note else {})}


def bukchon_with_stored_alternates():
    home, jongmyo, park, road = spot("북촌한옥마을"), spot("종묘"), spot("흥인지문공원"), spot("율곡로")
    item = Item(item_id=uuid4(), seq=1, kind="activity", title="북촌한옥마을", place_id=home["place_id"], place=home,
                starts_at=datetime(2030, 1, 1, 10, tzinfo=KST), ends_at=datetime(2030, 1, 1, 11, 30, tzinfo=KST),
                detail={"alternates": [alternate(jongmyo), alternate(park), alternate(road, "10:30으로 늦추면")]})
    places = {p["place_id"]: p for p in (home, jongmyo, park, road)}
    return item, places


def swap(item, places, choice=None):
    return plan_swap(trip_version=1, base_version=1, items=[item], places_by_id=places, item_id=item.item_id, choice=choice,
                     message="다른 곳으로 바꿔줘", request_id="r", check=None, customer_pick=True)


def test_auto_swap_lists_the_remaining_alternates_and_hands_them_on():
    item, places = bukchon_with_stored_alternates()
    plan = swap(item, places)
    text = plan.notice["text"]
    assert "종묘(으)로 바꿨습니다" in text and "다른 안: 1) 흥인지문공원 · 2) 10:30으로 늦추면 율곡로" in text, text
    assert [m["name"] for m in plan.summary["more_options"]] == ["흥인지문공원", "율곡로"]      # 원래 곳(북촌)은 되돌리기 몫
    assert plan.summary["kind"] == "activity"


def test_a_picked_alternate_does_not_reopen_the_list():
    item, places = bukchon_with_stored_alternates()
    pick = item.detail["alternates"][1]["key"]
    plan = swap(item, places, choice=pick)
    assert "다른 안" not in plan.notice["text"] and "more_options" not in plan.summary


def _response(monkeypatch, decision, status="resolved"):
    case = {"status": status, "version": 3, "intent": "other", "issue_code": "other",
            "state_json": {"decisions": [decision], "applied_actions": [{"result_ref": "trip:t:v3"}], "answer": "바꿨어요"}}

    @contextmanager
    def connection():
        yield None
    monkeypatch.setattr(case_dispatch, "get_connection", connection)
    monkeypatch.setattr(case_dispatch.repository, "get_case", lambda conn, **kw: case)
    return case_dispatch.response(tenant="t", case_id=uuid4(), execution={})


def test_adjusted_answer_with_other_options_carries_choices(monkeypatch):
    more = [{"name": "계림식당", "key": "a"}, {"name": "지금 여기가 맨 앞", "key": "b"}, {"name": "빠우", "key": "c", "note": "12:30으로 늦추면"}]
    got = _response(monkeypatch, {"itinerary": "customer_request", "to": "하나면옥", "kind": "dining", "more_options": more})
    assert got["status"] == "adjusted" and got["choices_title"] == "다른 안"
    # contract_correction `[2026-10-26 x600 40231a56]`: was 「식당 12:30으로 늦추면 빠우」 — the label is the place name only, the note is separate
    assert [c["label"] for c in got["choices"]] == ["식당 계림식당", "식당 지금 여기가 맨 앞", "식당 빠우"]
    assert [c.get("note") for c in got["choices"]] == [None, None, "12:30으로 늦추면"]
    assert got["choices"][0]["message"] == "하나면옥 대신 계림식당(으)로 바꿔 줘"


def test_adjusted_answer_without_other_options_has_no_choices(monkeypatch):
    got = _response(monkeypatch, {"itinerary": "customer_request", "to": "하나면옥", "kind": "dining", "more_options": []})
    assert "choices" not in got


def test_time_only_rollback_says_the_time_with_the_shown_title():
    place = {"place_id": str(uuid4()), "name": "남산서울타워"}
    old = Item(item_id=uuid4(), seq=4, kind="activity", title="N서울타워", place_id=place["place_id"], place=place,
               starts_at=datetime(2030, 1, 1, 19, tzinfo=KST), ends_at=datetime(2030, 1, 1, 20, tzinfo=KST))
    moved = replace(old, item_id=uuid4(), starts_at=datetime(2030, 1, 1, 20, tzinfo=KST), ends_at=datetime(2030, 1, 1, 21, tzinfo=KST))
    plan = plan_rollback(trip_version=2, base_version=2, current_items=[moved], old_items=[old], to_version=1,
                         message="방금 변경을 되돌려줘", request_id="r")
    assert plan.notice["text"] == "N서울타워 시각을 19:00 시작으로 되돌렸어요.", plan.notice["text"]
