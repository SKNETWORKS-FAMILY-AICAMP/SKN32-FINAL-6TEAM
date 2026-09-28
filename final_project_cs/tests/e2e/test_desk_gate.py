# -*- coding: utf-8 -*-
"""고객 신고(늦음 · 휴무)도 감시와 **같은 판정 문**을 지난다. `[2026-09-25]` D-020

★신고는 「문제가 생겼다」이지 「이 안으로 바꿔 달라」가 아니다 — 어느 안으로 바꿀지는 우리가 고른다.
  그래서 15번 「먼저 물어봐줘」면 묻고, 「변경 안 할 일정」이면 15번과 상관없이 묻는다.
★고객이 **직접 고른 것**(다른 안으로 · 되돌리기 · 제안 고르기)은 판정 문을 지나지 않는다.

재현:

    python -m pytest tests/e2e/test_desk_gate.py -v
"""
from __future__ import annotations

from app.modules.travel_ops.survey import SURVEY_VERSION

from .test_trip_api import SCENARIO, _body, _detail, _report, _say, api  # noqa: F401

ASK_FIRST = {"survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}}


def _create(api, *, pin_seq=None, **constraints):
    body = _body(api["customer"], request_id=f"gate-{pin_seq}-{len(constraints)}")
    if constraints:
        body["constraints"] = {**body["constraints"], **constraints}
    if pin_seq is not None:
        for item in body["items"]:
            if item["seq"] == pin_seq:
                item["detail"] = {**(item.get("detail") or {}), "customer_pinned": True}
    response = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))
    assert response.status_code == 201, response.text
    return response.json()["trip_id"]


def _proposals(api, trip_id):
    return api["client"].get(f"/v1/trips/{trip_id}/proposals",
                             headers=api["auth"]("trip:read")).json()["proposals"]


def test_without_ask_first_a_report_still_changes_the_plan_right_away(api):
    """기본(15번 없음) — 지금까지처럼 최고 안을 바로 적용한다."""
    trip_id = _create(api)
    closed = _report(api, trip_id, "closed").json()
    assert closed["status"] == "adjusted" and closed["to"] == "서울역 한식당(시나리오)"
    assert _proposals(api, trip_id) == []


def test_ask_first_turns_a_closed_report_into_a_question(api):
    trip_id = _create(api, **ASK_FIRST)
    asked = _report(api, trip_id, "closed").json()
    assert asked["status"] == "asked" and asked["reason"] == "ask_first" and asked["already"] is False
    assert asked["notice"]["type"] == "proposal_request"
    assert "답이 없으면 원래 일정을 그대로 둡니다" in asked["notice"]["text"]
    assert _detail(api, trip_id)["version"] == 1                    # ★바꾸지 않았다
    [proposal] = _proposals(api, trip_id)
    assert proposal["status"] == "open" and proposal["options"][0]["name"] == "서울역 한식당(시나리오)"
    # 알림이 바깥함에 있다 — 한 번
    sent = [key for key, payload in api["notices"]() if payload.get("proposal_id") == asked["proposal_id"]]
    assert sent == [f"{trip_id}:proposal:{asked['proposal_id']}"]

    # 같은 신고를 다시 보내도 제안은 하나 — 다시 묻지 않는다
    again = _report(api, trip_id, "closed", request_id="report-closed-2").json()
    assert again["status"] == "asked" and again["already"] is True
    assert again["proposal_id"] == asked["proposal_id"] and len(_proposals(api, trip_id)) == 1

    # 고르면 그때 바뀐다 — 고객이 고른 것은 판정 문을 지나지 않는다
    chosen = api["client"].post(f"/v1/trips/{trip_id}/proposals/{asked['proposal_id']}/choose",
                                json={"key": proposal["options"][0]["key"]},
                                headers=api["auth"]("trip:write"))
    assert chosen.status_code == 200 and chosen.json()["version"] == 2


def test_a_pinned_item_is_asked_about_even_without_ask_first(api):
    """★「변경 안 할 일정」 — 15번 답과 상관없이 묻는다. 늦음 신고(요식-P3)가 점심을 건드린다."""
    lunch = next(item["seq"] for item in SCENARIO["items"] if item["start"] == "13:00")
    trip_id = _create(api, pin_seq=lunch)
    asked = _report(api, trip_id, "delay").json()
    assert asked["status"] == "asked" and asked["reason"] == "protected"
    assert asked["protected_by"] == "customer_pinned"
    assert "바꾸지 않았어요" in asked["notice"]["text"]
    assert _detail(api, trip_id)["version"] == 1


def test_a_customer_sentence_that_ends_in_a_question_closes_the_case(api):
    """자유 문장 경로 — 물었으면 처리한 것이다. Case 는 닫히고(사람에게 넘기지 않는다) 답은 묻는 문장이다."""
    trip_id = _create(api, **ASK_FIRST)
    said = _say(api, trip_id, "closed").json()
    assert said["status"] == "asked" and said["case_status"] == "resolved", said
    assert _detail(api, trip_id)["version"] == 1
