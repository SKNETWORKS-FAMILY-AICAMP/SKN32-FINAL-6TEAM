# -*- coding: utf-8 -*-
"""대상 없이 맡긴 되묻기(담당 = `activity` 자리 표시)의 답이 고른 일정의 팀으로 넘어간다 — 장소 이름으로 답해도.

`[2026-10-26 라우팅 감사 6번]` `trip_messages._dispatch_decision` 은 대상이 없는 업무를 `activity` 에 맡기고, 답이 오면
`case_dispatch._resume_route` 가 고른 일정의 종류로 다시 넘긴다. 팀 쪽(`conversation_work._target`)은 일정 id · 제목 · **장소 이름**으로
대상을 찾는데 다시 넘기는 쪽은 id · 제목만 봤다 — 식당 장소 이름으로 답하면 `activity` 에 남아 `target_kind_mismatch` 로 사람에게 넘어갔다.
같은 일치 규칙(정확히 하나일 때만)을 쓴다. DB 없음 — 일정 읽기만 대역.
"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import case_dispatch
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 9, 30, tzinfo=KST)


def _item(kind, title, hour, place_name):
    return Item(item_id=uuid4(), seq=hour, kind=kind, title=title, place_id=None,
                starts_at=DAY + timedelta(hours=hour), ends_at=DAY + timedelta(hours=hour + 1),
                locked=False, booking_id=None, replaces_item_id=None, detail={},
                place={"place_id": str(uuid4()), "name": place_name, "kind": kind})


LUNCH = _item("dining", "점심", 12, "무구옥")
PALACE = _item("activity", "고궁 관람", 10, "경복궁")
TWIN_A = _item("dining", "저녁", 18, "같은집")
TWIN_B = _item("dining", "야식", 21, "같은집")
ITEMS = [PALACE, LUNCH, TWIN_A, TWIN_B]


@pytest.fixture(autouse=True)
def stored_items(monkeypatch):
    monkeypatch.setattr(case_dispatch, "get_connection", lambda: nullcontext(None))
    monkeypatch.setattr(TripStore, "latest", lambda self, conn, trip_id: ({}, list(ITEMS)))


def _waiting_clarify():
    request = {"type": "conversation", "action": "clarify", "question": "어느 일정을 바꿀까요?", "choices": []}
    return {"tenant_id": "fixture", "owner_team_id": "activity",
            "state_json": {"subject_ref": {"id": str(uuid4()), "request": request},
                           "required_input_schema": {"required": ["message"], "choices": [],
                                                     "x-conversation": {"request": request}}}}


def test_reply_naming_a_meal_place_goes_to_dining():
    assert case_dispatch._resume_route(_waiting_clarify(), "무구옥") == "dining"


def test_reply_by_title_or_id_still_routes_as_before():
    assert case_dispatch._resume_route(_waiting_clarify(), "고궁 관람") == "activity"
    assert case_dispatch._resume_route(_waiting_clarify(), str(LUNCH.item_id)) == "dining"


def test_ambiguous_place_name_is_not_guessed():
    """같은 장소 이름이 둘이면 고르지 않는다 — 지금 담당이 다시 묻는다(팀 쪽 `_target` 과 같은 규칙)."""
    assert case_dispatch._resume_route(_waiting_clarify(), "같은집") is None


def test_unrelated_reply_keeps_the_current_owner():
    assert case_dispatch._resume_route(_waiting_clarify(), "아직 모르겠어요") is None
