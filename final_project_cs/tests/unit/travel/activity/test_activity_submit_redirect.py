# -*- coding: utf-8 -*-
"""일정 제출은 여행 접수로 안내하고, 「바꿔 주세요」는 변경 제안으로 — `[2026-10-09]` team 통합 ⑥ · 조정 거부 연결.

전에는 일정 제출(`itinerary_submit`)을 받을 capability 가 없어 기본값(성립 판정)으로 갔고, 고객의 가장 임박한 예약을
판정해 엉뚱한 답을 냈다. 일정은 develop 여행 접수(`POST /v1/web/trip-intakes`)가 만든다 — 활동 팀은 예약을 읽지 않고 안내만.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.context import PolicyChunk
from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam

from ..helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools


def test_the_capability_is_declared_and_does_not_need_policy():
    assert "activity.submit_itinerary" in ActivityTeam.manifest.capabilities
    assert "activity.submit_itinerary" in ActivityTeam.manifest.policy_optional_capabilities


def test_an_itinerary_submission_is_routed_to_the_redirect():
    assert ActivityTeam.select_capability("itinerary_submit", "내일 3시에 경복궁 가요", {}) == "activity.submit_itinerary"


def test_a_case_about_a_trip_still_goes_to_itinerary_management():
    state = {"subject_ref": {"kind": "trip", "id": "t1"}}
    assert ActivityTeam.select_capability("itinerary_submit", "일정 바꿀게요", state) == "activity.itinerary"


def test_a_change_request_goes_to_the_change_proposal():
    """★`[2026-10-09]` 「바꿔 주세요」 — 전에는 성립 판정으로 가서 「성립합니다」로 답했다."""
    assert ActivityTeam.select_capability("adjust_reject", "다른 시간으로 바꿔 주세요", {}) == "activity.propose_change"


def test_a_change_request_about_a_trip_still_goes_to_itinerary_management():
    state = {"subject_ref": {"kind": "trip", "id": "t1"}}
    assert ActivityTeam.select_capability("adjust_reject", "다른 데로 바꿔 줘", state) == "activity.itinerary"


def test_a_change_request_makes_a_booking_change_proposal():
    tools = FakeTools({"read.booking": {"booking_id": "b1", "place_id": "p1",
                                        "starts_at": datetime.now(timezone.utc) + timedelta(hours=30)},
                       "read.policy": [PolicyChunk(document_id="t_doc_01", chunk_no=1, scope="travel_activity",
                                                   score=0.7, content="변경은 업체 조건을 따른다.")]})
    request = task("activity", "activity.propose_change", pack("activity", scope=["activity"]), ALLOWED)
    result = asyncio.run(ActivityTeam(tools).execute(request))

    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert [p.action_type for p in result.action_proposals] == ["booking.change"]


def test_other_intents_keep_the_default():
    assert ActivityTeam.select_capability("confirm_request", "성립하나요", {}) is None


def test_the_redirect_reads_no_booking_and_makes_no_proposal():
    tools = FakeTools({"read.booking": {"booking_id": "b1"}})
    request = task("activity", "activity.submit_itinerary", pack("activity", scope=["activity"]), ALLOWED)
    result = asyncio.run(ActivityTeam(tools).execute(request))

    assert tools.calls == []
    assert result.outcome == "completed" and result.next_action is NextAction.RESPOND
    assert not result.action_proposals
    assert result.decisions[0] == {"itinerary": "submit_redirected", "handled_by": "trip_intake",
                                   "entry": "POST /v1/web/trip-intakes"}
    assert "여행 일정 화면" in result.answer and result.evidence
