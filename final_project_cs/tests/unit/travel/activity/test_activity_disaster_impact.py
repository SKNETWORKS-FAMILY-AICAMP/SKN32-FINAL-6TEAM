# -*- coding: utf-8 -*-
"""재난문자가 활동을 막는가 — 유스케이스 수정본 §8 재해 분류표(D2 · 구현 계획 2.4). `[2026-10-11]`

기준은 등급이 아니라 재해의 성격이다. 지역 위험형은 그 구의 실내 · 야외를 모두 막고, 야외 위험형은 야외만 막는다
(실내외를 모르면 고객에게 묻는다). 반영 안 함은 막지 않고, 분류되지 않은 구분은 근거 · 경고로만 남긴다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import failure_codes as fc
from app.domains.travel_ops.instances.activity.disaster_impact import (
    IGNORED, OUTDOOR, REGION, UNCLASSIFIED, ImpactRules, assess)

from ..helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
STARTS = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
OPEN_HOURS = {"known": True, "attributes": {"hours_week": {"tue": {"open": "09:00", "close": "18:00"}}},
              "source": "tour_api", "why_unknown": None, "conditions": [], "usetime_text": None, "restdate_text": None}
#: 공유 점검은 재난문자 항목을 `ok` 로만 답한다 — 실내 장소면 날씨형 문자를 미리 빼서 이상으로 세지 않는다.
REPORT = {"verdict": "clear", "disruptions": [], "advisories": [], "failed_categories": [], "not_connected": [],
          "checks": [{"category": "disaster_msg", "status": "ok", "unclassified": []}]}


def _message(kind, text="", step="안전안내"):
    return {"kind": kind, "step": step, "text": text or f"{kind} 관련 안내", "created_at": "2026-11-10T12:00:00+09:00",
            "regions": ["서울특별시 종로구"], "serial": "1"}


def _run(messages, *, sensitive=False, report=REPORT, disaster="same"):
    found = {"for_region": list(messages), "unclassified": [], "covered": True} if disaster == "same" else disaster
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": STARTS, "party_size": 2, "capacity": 4},
              "read.policy": [],
              "read.place": {"place_id": "p1", "name": "경복궁", "weather_sensitive": sensitive,
                             "latitude": 37.5796, "longitude": 126.9770},
              "read.place_class": None,
              "read.disruptions": report, "read.disaster": found,
              "read.place_hours": OPEN_HOURS, "read.holiday": None}
    tools = FakeTools(values)
    result = asyncio.run(ActivityTeam(tools).execute(
        task("activity", "activity.check_feasible", pack("activity", scope=["activity"]), ALLOWED)))
    return result, [name for name, _ in tools.calls]


# ── 분류표(가드레일 한 곳) ──────────────────────────────────────

@pytest.mark.parametrize(("kind", "expected"), [
    ("산사태", REGION), ("호우", REGION), ("민방공", REGION), ("교통통제", REGION), ("화학물질 유출", REGION),
    ("미세먼지", OUTDOOR), ("폭염", OUTDOOR), ("황사", OUTDOOR),
    ("기타", IGNORED), ("실종", IGNORED), ("건조", IGNORED),
    ("감염병", UNCLASSIFIED), ("새로운구분", UNCLASSIFIED),
])
def test_the_table_follows_section_8(kind, expected):
    assert ImpactRules.load().kind_class(kind) == expected


def test_drill_and_release_texts_are_not_counted():
    rules = ImpactRules.load()
    assert rules.kind_class("민방공", "민방위 훈련 — 실제 상황이 아닙니다") == IGNORED
    assert rules.kind_class("교통통제", "통제가 완전 해제되었음") == IGNORED


@pytest.mark.parametrize(("outdoor", "blocks", "ask", "no_effect"), [
    (True, 2, 0, 0), (False, 1, 0, 1), (None, 1, 1, 0)])
def test_outdoor_only_hazards_depend_on_the_place(outdoor, blocks, ask, no_effect):
    impact = assess([_message("산사태"), _message("폭염")], outdoor, ImpactRules.load())
    assert (len(impact.blocks), len(impact.ask), len(impact.no_effect)) == (blocks, ask, no_effect)


# ── 성립 판정 ─────────────────────────────────────────────────

def test_regression_4_landslide_in_the_same_district_blocks_an_indoor_heritage_site():
    """회귀 ④ — 종로구 인왕산 등산로 산사태 vs 경복궁. 지역 위험형이라 그 구 전체(실내 포함)를 막는다(D2 — 기대값 `blocks`).
    ★공유 점검은 실내 장소면 날씨형 문자(산사태)를 미리 빼서 이상으로 세지 않는다 — 다시 읽어야 보인다."""
    result, calls = _run([_message("산사태", "종로구 인왕산 등산로 산사태 발생, 입산 통제", step="긴급재난")])
    decision = result.decisions[0]
    assert "read.disaster" in calls
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert decision["feasible"] is False and decision["reason"] == "disaster_blocks"
    assert decision["failure_code"] == fc.DISASTER_BLOCKS
    assert decision["disaster"]["blocks"] is True and decision["disaster"]["blocking"][0]["impact"] == REGION
    assert "alternatives" in decision          # ★장소를 바꾸면 풀리는 사유다 — 대체 후보를 찾는다(UC-A4)


def test_an_outdoor_only_hazard_does_not_block_an_indoor_place():
    result, _ = _run([_message("미세먼지")], sensitive=False)
    assert result.outcome == "completed" and result.decisions[0]["feasible"] is True


def test_an_outdoor_only_hazard_blocks_an_outdoor_place():
    result, _ = _run([_message("미세먼지")], sensitive=True)
    assert result.decisions[0]["reason"] == "disaster_blocks"


def test_an_outdoor_only_hazard_with_unknown_indoor_asks_the_customer():
    """수정본 UC-A3 `3b2` — 계획 검증에서는 야외인지 묻는다."""
    result, _ = _run([_message("폭염")], sensitive=None)
    assert result.outcome == "waiting" and result.next_action is NextAction.WAIT_FOR_INPUT
    assert result.required_input_schema["required"] == ["outdoor"]
    assert result.decisions[0]["reason"] == "indoor_unknown_weather"


def test_an_ignored_kind_does_not_block():
    result, _ = _run([_message("실종", "실종자를 찾습니다")])
    assert result.decisions[0]["feasible"] is True and not result.warnings


def test_an_unclassified_kind_is_kept_as_a_warning_not_a_block():
    """수정본 UC-A3 `3b4` — 막지 않고 「분류되지 않은 재해구분」 경고."""
    result, _ = _run([_message("감염병")])
    assert result.decisions[0]["feasible"] is True
    assert any("분류되지 않은 재해구분(감염병)" in w for w in result.warnings)


def test_messages_that_cannot_be_reread_are_not_read_as_no_effect():
    """재난 사실을 최신으로 확인하지 못하면 「영향 없음」이 아니라 운영 담당자에게 넘긴다(구현 계획 §2.5-E)."""
    for missing in (None, {"covered": False}):
        result, _ = _run([], disaster=missing)
        assert result.outcome == "escalated" and result.failure_code == fc.DISASTER_UNCONFIRMED


def test_no_reread_when_the_shared_check_has_no_disaster_source():
    """재난문자 소스가 미연결이면 분류하지 않는다 — 공유 점검 판정(미연결 표시) 그대로다."""
    report = {**REPORT, "checks": [{"category": "disaster_msg", "status": "not_connected"}]}
    result, calls = _run([], report=report, disaster=None)
    assert "read.disaster" not in calls and result.decisions[0]["feasible"] is True


def test_a_safety_stop_still_wins_and_offers_no_alternatives():
    """재난 정지 대상(여행 전체)은 §8 보다 먼저다 — 정지는 대체 장소를 붙이지 않는 결정이다."""
    result, calls = _run([_message("민방공", "민방공 상황 발령, 안내에 따라 대피하십시오", step="위급재난")])
    decision = result.decisions[0]
    assert decision["reason"] == "safety_event" and "alternatives" not in decision
    assert "read.place_candidates" not in calls


def test_the_disaster_tools_are_declared():
    assert "read.disaster" in ALLOWED and "read.disaster_points" in ALLOWED


# ── 대체 후보 재확인(UC-A4 2단계) ──────────────────────────────────

def _candidate_rows():
    return {"indoor": {"contentid": "indoor", "lclsSystm1": "VE", "lclsSystm2": "VE07", "mapx": "127.0", "mapy": "37.5"},
            "outdoor": {"contentid": "outdoor", "lclsSystm1": "NA", "lclsSystm2": "NA01", "mapx": "127.0", "mapy": "37.5"}}


def _recheck(messages):
    rows = _candidate_rows()
    ranked = {"alternatives": [{"contentid": "indoor", "revalidated": True}, {"contentid": "outdoor", "revalidated": True}],
              "more_alternatives": []}
    point = {"for_region": list(messages), "unclassified": [], "covered": True}
    tools = FakeTools({"read.disaster_points": {"points": [point, point]}})
    team = ActivityTeam(tools)
    t = task("activity", "activity.check_feasible", pack("activity", scope=["activity"]), ALLOWED)
    _, note = team._recheck_disaster(t, ranked, list(rows.values()), STARTS, set(), [])
    return [a["contentid"] for a in ranked["alternatives"]], note


def test_candidate_recheck_drops_every_candidate_under_a_region_wide_hazard():
    kept, note = _recheck([_message("호우")])
    assert kept == [] and note == "all_blocked"


def test_candidate_recheck_keeps_indoor_candidates_under_an_outdoor_only_hazard():
    kept, _ = _recheck([_message("미세먼지")])
    assert kept == ["indoor"]


# ── `[2026-10-11 사용자 결정]` 표 앞의 세 규칙(골든셋 검수 disaster-03 · 09 · 10) ─────────────

def _at(hour):
    return datetime(2026, 10, 14, hour, 0, tzinfo=KST)


def _sent(kind, text, created="2026-10-14T05:30:00+09:00"):
    return {"kind": kind, "step": "긴급재난", "text": text, "created_at": created}


def test_a_message_naming_the_place_closed_blocks_even_as_etc():
    """disaster-03 — 「기타」여도 그 장소의 관람 전면 중단이면 가도 못 본다."""
    msg = _sent("기타", "[국가유산청] 경복궁 일대 시설 점검으로 금일 경복궁 관람 전면 중단")
    impact = assess([msg], False, ImpactRules.load(), at=_at(14), place_name="경복궁")
    assert impact.blocks and impact.blocks[0]["impact"] == "place_closed"


def test_a_closure_naming_another_place_does_not_block():
    msg = _sent("기타", "[국가유산청] 경복궁 일대 시설 점검으로 금일 경복궁 관람 전면 중단")
    assert not assess([msg], False, ImpactRules.load(), at=_at(14), place_name="창덕궁").blocks


def test_a_recovery_message_does_not_block():
    """disaster-09 — 「복구가 완료」는 상황이 끝났다는 말이다."""
    msg = _sent("정전", "[송파구] 잠실동 일대 정전 복구가 완료되었습니다")
    impact = assess([msg], False, ImpactRules.load(), at=_at(14), place_name="롯데월드 어드벤처")
    assert not impact.blocks and impact.no_effect


@pytest.mark.parametrize(("hour", "blocks"), [(14, False), (10, True), (5, False)])
def test_a_control_window_blocks_only_inside_it(hour, blocks):
    """disaster-10 · 11 — 통제 06~12시. 문제가 생긴 시각에만 막는다."""
    msg = _sent("호우", "[서울시] 호우경보로 한강공원 전면 통제 (10/14 06:00~10/14 12:00)")
    impact = assess([msg], True, ImpactRules.load(), at=_at(hour), place_name="여의도한강공원")
    assert bool(impact.blocks) is blocks


def test_an_unreadable_window_falls_back_to_the_table():
    """통제 시간을 못 읽으면 「끝났다」로 짐작하지 않는다 — 표대로 막는다."""
    msg = _sent("호우", "[서울시] 호우경보로 한강공원 통제 중")
    assert assess([msg], True, ImpactRules.load(), at=_at(14)).blocks


def test_the_golden_disaster_cases_agree_with_the_decided_labels():
    """골든셋 재난 문항(1차 라벨 · 사용자 결정 반영)을 이 규칙으로 다시 판정한다. 지역 거르기(다른 구 · 부산)는 공유 점검 몫이라 뺀다."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    cases = [json.loads(line) for line in (root / "eval/activity_judge/cases.jsonl").read_text(encoding="utf-8").splitlines()]
    first = json.loads((root / "eval/activity_judge/labels_first_pass.json").read_text(encoding="utf-8"))["labels"]
    outdoor = {"경복궁": False, "남산공원": True, "망원한강공원": True, "롯데월드 어드벤처": False, "여의도한강공원": True}
    rules = ImpactRules.load()
    for case in cases:
        if case["kind"] != "disaster_effect" or case["case_id"] in ("disaster-02", "disaster-08"):
            continue
        i = case["inputs"]
        impact = assess(i["messages"], outdoor[i["place_name"]], rules,
                        at=datetime.fromisoformat(i["starts_at"]), place_name=i["place_name"])
        got = "blocks" if impact.blocks else "no_effect"
        assert got in first[case["case_id"]]["acceptable"], (case["case_id"], got)
