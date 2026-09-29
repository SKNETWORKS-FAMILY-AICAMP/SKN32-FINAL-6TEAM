# -*- coding: utf-8 -*-
"""활동 팀 PR #6 에서 가져온 장점과, 비교하며 찾은 우리 쪽 약점의 수정. `[2026-09-29]`

기록 — `wiki/records/reports/2026-09-28_1826_Activity_PR6_전수검수_리포트.md`

① 대체 활동은 「비슷한 곳(관광공사 분류·구) → 가까운 곳」 순이다. ★순위만 바꾼다 — 거르지 않는다.
② 설문 우선순위가 선호를 정한다(activity 먼저 = 분류, mobility 먼저 = 구).
③ 이미 시작한 예약은 성립을 다시 점검하지 않는다.
④ 예약 경로의 변경 제안은 **실행기가 있는** `booking.change` 로 낸다(전에는 `activity.change` — 실행기 없음).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

import pytest

from app.core.context import PolicyChunk
from app.core.contracts import NextAction
from app.modules.travel_ops.activity import ActivityTeam
from app.modules.travel_ops.activity.similarity import preference_of, score
from app.modules.travel_ops.replan import activity_candidates, choose

from ..helpers import FakeTools, in_hours, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
AT = datetime(2026, 10, 3, 14, tzinfo=ZoneInfo("Asia/Seoul"))   # 영업시간은 현지 시각으로 본다


def _place(pid, *, lat, lon, cls=None, price=10_000, indoor=True):
    return {"place_id": pid, "name": pid, "kind": "activity", "latitude": lat, "longitude": lon,
            "catalog_class": cls,
            "attributes": {"price_krw": price, "indoor": indoor, "hours": ["09:00", "18:00"]}}


ORIGIN = _place("origin", lat=37.5700, lon=126.9800,
                cls={"lcls1": "VE", "lcls2": "VE01", "lcls3": "VE0101", "sigungu": "23"})


# ── ① 점수 ─────────────────────────────────────────────────────
def test_unknown_values_never_count_as_the_same():
    assert score(None, ORIGIN["catalog_class"]) == 0
    assert score({"lcls1": ""}, {"lcls1": ""}) == 0


def test_the_first_field_outweighs_all_later_fields():
    """「활동 중요」 순서는 lcls1 → 구 → lcls2 → lcls3. 앞 하나가 뒤 셋의 합보다 무겁다."""
    same_class = {"lcls1": "VE"}
    same_rest = {"sigungu": "23", "lcls2": "VE01", "lcls3": "VE0101"}   # lcls1 만 다르다
    assert score(ORIGIN["catalog_class"], same_class) > score(ORIGIN["catalog_class"], same_rest)


def test_mobility_first_puts_the_district_first():
    near = {"sigungu": "23"}
    alike = {"lcls1": "VE"}
    origin = ORIGIN["catalog_class"]
    assert score(origin, near, "mobility") > score(origin, alike, "mobility")
    assert score(origin, alike, "activity") > score(origin, near, "activity")


def test_preference_follows_the_survey_priority():
    assert preference_of({"survey": {"priority": ["food", "mobility", "activity"]}}) == "mobility"
    assert preference_of({"survey": {"priority": ["activity"]}}) == "activity"
    assert preference_of({"survey": {"priority": ["food"]}}) is None
    assert preference_of(None) is None


# ── ① 순위 — 거르지 않고 줄만 세운다 ────────────────────────────
def _candidates(similarity):
    places = [
        _place("near_other", lat=37.5705, lon=126.9800, cls={"lcls1": "SH", "sigungu": "23"}),   # 약 55m
        _place("far_alike", lat=37.5740, lon=126.9800, cls={"lcls1": "VE", "lcls2": "VE01",
                                                            "sigungu": "23"}),                     # 약 445m
        _place("no_class", lat=37.5702, lon=126.9800),                                            # 약 22m
    ]
    return activity_candidates(original=ORIGIN, places=places, start=AT, end=AT + timedelta(hours=1),
                               causes=[], similarity=similarity)


def test_similar_place_comes_first_then_distance():
    best, alternates, rejected = choose(_candidates(partial(score, preference="activity")))
    assert not rejected
    assert [best.key, *[c.key for c in alternates]] == ["far_alike", "near_other", "no_class"]


def test_without_similarity_the_closest_wins_and_nobody_is_dropped():
    """점수가 없으면(식당·예전 호출) 비용이 같을 때 가까운 곳 — 전에는 장소 id 순이었다."""
    best, alternates, _ = choose(_candidates(None))
    assert [best.key, *[c.key for c in alternates]] == ["no_class", "near_other", "far_alike"]


def test_similarity_never_rescues_a_rejected_candidate():
    closed = _place("alike_but_closed", lat=37.5701, lon=126.9800,
                    cls=dict(ORIGIN["catalog_class"]))
    closed["attributes"].pop("hours")          # 영업시간 모름 → 우리 규칙대로 탈락
    out = activity_candidates(original=ORIGIN, places=[closed], start=AT, end=AT + timedelta(hours=1),
                              causes=[], similarity=score)
    best, _, rejected = choose(out)
    assert best is None and [c.key for c in rejected] == ["alike_but_closed"]


# ── ③·④ 예약 경로 ─────────────────────────────────────────────
def _booking_values(starts_at, report):
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": starts_at,
                         "party_size": 2, "capacity": 4},
        "read.policy": [PolicyChunk(document_id="t_doc_01", chunk_no=1, scope="travel_activity", score=0.7,
                                     content="취소·환급은 업체 조건을 따른다.")],
        "read.place": {"place_id": "p1", "weather_sensitive": True, "latitude": 37.5, "longitude": 127.0},
        "read.disruptions": report,
    }


@pytest.mark.asyncio
async def test_an_activity_that_already_started_is_not_rechecked():
    tools = FakeTools(_booking_values(datetime.now(UTC) - timedelta(hours=3), None))
    context = pack("activity", scope=["activity"])
    result = await ActivityTeam(tools).execute(task("activity", "activity.check_feasible", context, ALLOWED))
    assert result.outcome == "completed" and result.next_action is NextAction.RESPOND
    assert result.decisions[0]["reason"] == "already_started"
    assert "read.disruptions" not in [name for name, _ in tools.calls]


@pytest.mark.asyncio
async def test_a_disrupted_booking_proposes_an_executable_change():
    report = {"verdict": "disrupted", "disruptions": [{"kind": "호우경보", "category": "weather_warning"}],
              "advisories": [], "checks": [], "failed_categories": [], "not_connected": []}
    context = pack("activity", scope=["activity"])
    result = await ActivityTeam(FakeTools(_booking_values(in_hours(30), report))).execute(
        task("activity", "activity.check_feasible", context, ALLOWED))
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert [p.action_type for p in result.action_proposals] == ["booking.change"]


def test_booking_change_has_a_registered_executor():
    from app.composition import build_action_handlers

    assert build_action_handlers().get("booking.change") is not None


# ── 비교 중 찾은 우리 쪽 약점 — 영업시간은 서울 시각으로 본다 ──────────
def test_opening_hours_are_read_in_seoul_time_whatever_the_timezone():
    """같은 순간(서울 14:00)이 UTC 로 들어와도 「영업 중」. 전에는 05:00 으로 읽어 「영업 전」이었다."""
    from app.modules.travel_ops.place_hours import fits

    attributes = {"hours": ["09:00", "18:00"]}
    in_utc = AT.astimezone(UTC)
    assert in_utc.hour == 5
    assert fits(attributes, in_utc, in_utc) is True
    assert fits(attributes, AT, AT) is True
