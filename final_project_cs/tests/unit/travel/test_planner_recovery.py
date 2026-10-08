# -*- coding: utf-8 -*-
"""재난 뒤 다시 짤 때 사용자가 고른 제약 둘 — 일정 생성기가 받는 방식. `[결정 2026-10-07 사용자]`

★`avoid_districts` — 피해 구의 장소를 후보에서 뺀다. 구를 **모르는** 후보는 빼지 않는다(모르는 것을 피해 구로 처리하지 않는다).
★`lighter_day` — **사용자가 `true` 로 골랐을 때만** 밀도 목표를 한 단계 낮춘다. 우리가 임의로 낮추지 않는다(낮추는 근거 연구가 없다).
  목표를 직접 줬거나(`target_density`) 없으면 낮출 기준이 없다 — 낮추지 않고 그 사실을 적는다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.planning.planner import Cand, PlanRefused, lighter_constraints, without_districts


def _cand(name, district):
    return Cand(key=name, name=name, kind="activity", lat=37.5, lon=127.0, attributes=({"district": district} if district else {}), origin="places")


# ── 오늘은 가볍게 ──────────────────────────────────────────────────
@pytest.mark.parametrize("level,lower", [("very_high", "high"), ("high", "normal"), ("normal", "low")])
def test_lighter_day_lowers_the_density_level_by_exactly_one_step(level, lower):
    out, note = lighter_constraints({"lighter_day": True, "density": {"level": level, "days": {}}})
    assert out["density"]["level"] == lower and out["density"]["days"] == {}
    assert note == {"requested": True, "applied": True, "from": level, "to": lower}


def test_the_lowest_level_stays_and_says_it_was_not_applied():
    out, note = lighter_constraints({"lighter_day": True, "density": {"level": "low"}})
    assert out["density"]["level"] == "low" and note["applied"] is False and note["to"] == "low"


def test_it_is_applied_only_when_the_user_chose_it():
    for constraints in ({}, {"lighter_day": False}, {"lighter_day": "yes"}, {"lighter_day": 1}, {"density": {"level": "high"}}):
        out, note = lighter_constraints(constraints)
        assert note is None and out == constraints, constraints                      # 글자 「yes」 · 1 을 참으로 읽지 않는다 · 밀도만 있으면 건드리지 않는다


def test_without_a_level_to_lower_nothing_is_invented():
    for constraints in ({"lighter_day": True}, {"lighter_day": True, "density": {"target_density": 0.6}},
                        {"lighter_day": True, "density": {"level": "high", "target_density": 0.6}}):
        out, note = lighter_constraints(constraints)
        assert note["requested"] is True and note["applied"] is False and "단계를 낮추지 않았다" in note["note"], constraints
        assert out.get("density") == constraints.get("density")                      # 목표를 직접 줬으면 그대로


# ── 피해 구 빼기 ───────────────────────────────────────────────────
def test_candidates_in_the_avoided_districts_are_dropped_and_unknown_ones_are_kept():
    pool = [_cand("강남 전시", "강남구"), _cand("송파 공원", "송파구"), _cand("마포 시장", "마포구"), _cand("구를 모르는 곳", None)]
    kept, note = without_districts(pool, ["강남구", "송파구"])
    assert [c.name for c in kept] == ["마포 시장", "구를 모르는 곳"]                       # 모르는 곳은 남긴다 — 피해 구로 처리하지 않는다
    assert note == {"avoid_districts": ["강남구", "송파구"], "excluded": 2, "kept_without_district": 1}


def test_nothing_changes_without_a_list_or_with_an_empty_one():
    pool = [_cand("강남 전시", "강남구")]
    assert without_districts(pool, None) == (pool, None)
    assert without_districts(pool, []) == (pool, None)
    assert without_districts(pool, ["", "  "]) == (pool, None)


@pytest.mark.parametrize("bad", ["강남구", 7, {"강남구": 1}, ["강남구", 3]])
def test_a_list_that_is_not_names_is_refused_not_guessed(bad):
    with pytest.raises(PlanRefused) as caught:
        without_districts([_cand("x", "강남구")], bad)
    assert caught.value.code == "invalid_avoid_districts"


# ── 웹 입구(읽기 뒤 일정 짜기)가 받는 모양 ─────────────────────────
def test_the_web_entry_accepts_only_seoul_district_names_and_a_real_boolean():
    from pydantic import ValidationError

    from app.domains.travel_ops.entry.trip_api import RecoveryPlanIn

    assert RecoveryPlanIn(avoid_districts=["강남구", "송파구"], lighter_day=True).lighter_day is True
    assert RecoveryPlanIn().avoid_districts == [] and RecoveryPlanIn().lighter_day is False
    for bad in ({"avoid_districts": ["부산진구"]}, {"avoid_districts": ["강남"]}, {"lighter_day": "yes"}, {"lighter_day": 1}, {"extra": 1}):
        with pytest.raises(ValidationError):
            RecoveryPlanIn(**bad)
