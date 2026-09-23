# -*- coding: utf-8 -*-
"""여행 시작 설문(`constraints.survey`) — 받는 모양과 **실제로 쓰는 몫**. `[2026-09-24]` D-020

★판정에 쓰는 것은 둘이다 — 15번 「일정이 꼬이면」(on_disruption)과 16번 「여유」(pace → 밀도 목표).
  나머지 문항은 받아 두기만 한다. 세부 선택지는 담당 팀이 정해서 알려 준다(2026-09-24 회의).

재현:

    python -m pytest tests/e2e/test_trip_survey.py -v
"""
from __future__ import annotations

import copy
from datetime import date

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.survey import SURVEY_VERSION, apply_survey, on_disruption

from .test_trip_api import DAY, _body, api  # noqa: F401 — 픽스처를 그대로 쓴다


def _stored_constraints(trip_id: str) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT constraints FROM trips WHERE trip_id=%s", (trip_id,))
        return cur.fetchone()[0]


def _with(api, request_id: str, **constraints):
    body = _body(api["customer"], request_id=request_id)
    body["constraints"] = {**copy.deepcopy(body["constraints"]), **constraints}
    body["constraints"].pop("density", None)
    return body


def _post(api, body):
    return api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))


def test_without_a_survey_nothing_changes(api):
    """★설문이 없는 여행은 지금까지와 똑같다 — 밀도를 지어내지 않는다."""
    view = _post(api, _with(api, "no-survey")).json()
    assert view["density"] == [] and "survey" not in _stored_constraints(view["trip_id"])


def test_pace_fills_the_density_target_and_the_team_default_day(api):
    """16번 🐢 여유롭게 → 목표 0.40, 하루 활동 시간은 팀 기본값 08:00~22:00."""
    view = _post(api, _with(api, "relaxed", survey={"version": SURVEY_VERSION, "pace": "relaxed"})).json()
    day = view["density"][0]
    assert day["target_density"] == 0.40
    assert day["available_minutes"] == 14 * 60                 # 08:00~22:00
    stored = _stored_constraints(view["trip_id"])
    assert stored["density"]["level"] == "low"
    assert "팀 기본값 08:00~22:00" in stored["derived"]["density"]   # 무엇을 채웠는지 남긴다


@pytest.mark.parametrize("pace,target", [("moderate", 0.55), ("packed", 0.70)])
def test_each_pace_maps_to_its_preset(api, pace, target):
    view = _post(api, _with(api, f"pace-{pace}", survey={"version": SURVEY_VERSION, "pace": pace})).json()
    assert view["density"][0]["target_density"] == target


def test_a_density_the_user_gave_wins_over_the_survey(api):
    """★사용자가 직접 준 밀도가 이긴다 — 설문은 빈 곳만 채운다."""
    window = {DAY: {"starts_at": f"{DAY}T10:00:00+09:00", "ends_at": f"{DAY}T20:00:00+09:00",
                    "buffer_minutes": 0}}
    body = _with(api, "user-wins", survey={"version": SURVEY_VERSION, "pace": "relaxed"})
    body["constraints"]["density"] = {"level": "high", "days": window}
    view = _post(api, body).json()
    assert view["density"][0]["target_density"] == 0.70
    assert view["density"][0]["available_minutes"] == 10 * 60


def test_a_density_without_a_target_takes_the_target_from_the_survey(api):
    window = {DAY: {"starts_at": f"{DAY}T10:00:00+09:00", "ends_at": f"{DAY}T20:00:00+09:00",
                    "buffer_minutes": 0}}
    body = _with(api, "fill-target", survey={"version": SURVEY_VERSION, "pace": "packed"})
    body["constraints"]["density"] = {"days": window}
    view = _post(api, body).json()
    assert view["density"][0]["target_density"] == 0.70
    assert view["density"][0]["available_minutes"] == 10 * 60   # 사용자의 시간은 그대로


@pytest.mark.parametrize("survey,field", [
    ({"version": SURVEY_VERSION, "on_disruption": "whatever"}, "on_disruption"),
    ({"version": SURVEY_VERSION, "pace": "slow"}, "pace"),
    ({"version": SURVEY_VERSION, "unknown_question": 1}, "unknown_question"),
    ({"pace": "relaxed"}, "version"),
])
def test_a_malformed_survey_is_refused_and_nothing_is_stored(api, survey, field):
    body = _with(api, f"bad-{field}", survey=survey)
    response = _post(api, body)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "invalid_survey"
    assert any(field in p["field"] for p in error["problems"]), error["problems"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 0


def test_team_defined_details_are_kept_as_given(api):
    """★세부 선택지는 팀이 정할 값이라 목록을 박지 않는다 — 받은 그대로 남긴다."""
    survey = {"version": SURVEY_VERSION, "on_disruption": "ask_first", "theme": "쇼핑·식도락",
              "party": "친구 2명", "preferred_mobility": ["대중교통", "도보"], "domestic": False,
              "priority": ["food", "activity"], "priority_details": {"food": ["맛", "청결"]},
              "indoor_outdoor": {"dining": "indoor", "activity": "any"}, "theme_details": ["팝업스토어"]}
    view = _post(api, _with(api, "details", survey=survey)).json()
    stored = _stored_constraints(view["trip_id"])["survey"]
    assert stored["priority_details"] == {"food": ["맛", "청결"]}
    assert stored["on_disruption"] == "ask_first" and stored["theme_details"] == ["팝업스토어"]


# ── 부품 ──────────────────────────────────────────────────────────
def test_the_default_reaction_is_the_current_behaviour():
    """★설문이 없거나 15번을 안 골랐으면 지금까지의 동작(바로 적용하고 알린다)이다."""
    assert on_disruption({}) == "replace"
    assert on_disruption(None) == "replace"
    assert on_disruption(apply_survey({"survey": {"version": SURVEY_VERSION}}, [])) == "replace"
    assert on_disruption({"survey": {"on_disruption": "ask_first"}}) == "ask_first"


def test_no_item_days_means_no_invented_window():
    out = apply_survey({"survey": {"version": SURVEY_VERSION, "pace": "relaxed"}}, [])
    assert "density" not in out


def test_the_filled_window_uses_every_item_day_once():
    out = apply_survey({"survey": {"version": SURVEY_VERSION, "pace": "moderate"}},
                       [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 1)])
    assert sorted(out["density"]["days"]) == ["2026-10-01", "2026-10-02"]
    assert out["density"]["days"]["2026-10-01"]["starts_at"] == "2026-10-01T08:00:00+09:00"
