"""예보 주의 → 알림과 변경 버튼 → 동의 후 후보 → 선택 후 변경. 실제 로컬 DB, 재생 입력."""
from __future__ import annotations

from copy import deepcopy
from uuid import UUID

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.planning.pending import (
    CONSENT_KEY, CONSENT_REASON, FORECAST_REASON, PendingStore, forecast_attention,
)
from app.domains.travel_ops.components.watch.trip_watch import TripWatcher
from tests.e2e.test_indoor_unknown_consent import _choose, _create_with, _proposals
from tests.e2e.test_trip_api import _at, _detail, _slot, api  # noqa: F401
from tests.scenario.test_case_version_day import case_world  # noqa: F401

ADVISORY = {"verdict": "clear", "disruptions": [], "advisories": [
    {"category": "forecast", "field": "precipitation_probability", "value": 80, "limit": 60},
    {"category": "forecast", "field": "wind_speed_kmh", "value": 35, "limit": 30}],
    "indoor_unknown": False}


def _check(**kwargs):
    return deepcopy(ADVISORY if kwargs["place"]["name"] == "잠실 스카이타워"
                    else {"verdict": "clear", "disruptions": [], "advisories": []})


def _watch(api, check=_check):
    return TripWatcher(store=api["store"], check=check, connection_factory=get_connection,
                       clock=lambda: _at("09:00"))


def _create(api):
    # 자동 변경을 직접 골랐어도 예보 주의만으로 바꾸지 않는다.
    return _create_with(api, {"survey": {"version": "2026-09-24.v1", "on_disruption": "replace"}})


def test_forecast_alone_creates_warning_and_consent_without_changing(api):
    trip_id = _create(api)
    tick = _watch(api).tick()
    assert tick.adjusted == [] and len(tick.asked) == 1
    [proposal] = _proposals(api, trip_id)
    assert proposal["reason"] == FORECAST_REASON and proposal["options_json"] == []
    notice = next(n for _, n in api["notices"]() if n.get("reason") == FORECAST_REASON)
    assert "예보 주의사항" in notice["text"] and "강수확률 80%" in notice["text"]
    assert "풍속 35km/h" in notice["text"] and "예보에 맞게 일정 변경" in notice["text"]
    assert notice["consent_key"] == CONSENT_KEY and notice["proposal_id"] == str(proposal["proposal_id"])
    assert notice["causes"] == ADVISORY["advisories"]
    assert _detail(api, trip_id)["version"] == 1


def test_consent_computes_indoor_options_and_only_choice_changes_itinerary(api):
    trip_id = _create(api)
    _watch(api).tick()
    [proposal] = _proposals(api, trip_id)
    shown = _choose(api, trip_id, proposal["proposal_id"], CONSENT_KEY, check=_check)
    assert shown["status"] == "options" and shown["options"]
    assert _detail(api, trip_id)["version"] == 1
    [filled] = _proposals(api, trip_id)
    assert filled["reason"] == f"{FORECAST_REASON}_options"
    pick = next(o["key"] for o in filled["options_json"] if o["name"] == "아쿠아리움")
    chosen = _choose(api, trip_id, proposal["proposal_id"], pick, check=_check)
    assert chosen["status"] == "chosen" and chosen["version"] == 2
    assert _slot(_detail(api, trip_id), 2)["place"] == "아쿠아리움"


@pytest.mark.parametrize("keep", [False, True])
def test_repeat_and_decline_do_not_create_another_warning(api, keep):
    trip_id = _create(api)
    watcher = _watch(api)
    watcher.tick()
    [proposal] = _proposals(api, trip_id)
    if keep:
        assert _choose(api, trip_id, proposal["proposal_id"], None) == {"status": "kept"}
    count = len(api["notices"]())
    assert watcher.tick().asked == []
    assert len(api["notices"]()) == count and len(_proposals(api, trip_id)) == 1
    assert _detail(api, trip_id)["version"] == 1


@pytest.mark.parametrize("keep", [False, True])
def test_confirmed_weather_is_not_blocked_by_forecast_proposal(api, keep):
    trip_id = _create_with(api, {"payment": "card"})  # 확정 사건도 먼저 묻는 고객
    _watch(api).tick()
    [proposal] = _proposals(api, trip_id)
    if keep:
        _choose(api, trip_id, proposal["proposal_id"], None)

    def confirmed(**kwargs):
        result = _check(**kwargs)
        if result["advisories"]:
            result.update(verdict="disrupted", disruptions=[{"category": "weather_warning", "kind": "호우주의보"}])
        return result

    tick = _watch(api, confirmed).tick()
    assert len(tick.asked) == 1
    proposals = _proposals(api, trip_id)
    assert len(proposals) == 2
    old = next(p for p in proposals if p["reason"] == FORECAST_REASON)
    assert old["status"] == ("kept" if keep else "superseded")
    assert next(p for p in proposals if p["reason"] == CONSENT_REASON)["status"] == "open"


@pytest.mark.parametrize("report", [
    {"verdict": "clear", "advisories": []},
    {**ADVISORY, "verdict": "fatal", "failed_categories": ["weather_warning"]},
    {"verdict": "clear", "advisories": [{"category": "earthquake"}]},
])
def test_clear_or_incomplete_or_other_advisory_is_not_a_forecast_proposal(api, report):
    trip_id = _create(api)
    _watch(api, lambda **_: report).tick()
    assert _proposals(api, trip_id) == [] and _detail(api, trip_id)["version"] == 1


def test_indoor_activity_is_not_offered_forecast_change(api):
    trip_id = UUID(_create(api))
    with get_connection() as conn, conn.transaction():
        _, items = api["store"].latest(conn, trip_id)
        item = next(i for i in items if i.place and i.place.get("weather_sensitive") is False)
        assert forecast_attention(conn, store=api["store"], trip_id=trip_id, item=item, report=ADVISORY) is None
    assert _proposals(api, trip_id) == []


def test_default_case_watch_also_notifies_forecast_without_running_case(case_world):
    world = case_world
    world["clock"].now = _at("09:00")
    world["engine"].opener.check = _check
    tick = world["engine"].tick()
    assert tick.opened == [] and tick.ran == [] and len(tick.notified) == 1
    with get_connection() as conn:
        assert world["store"].latest(conn, world["trip_id"])[0]["version"] == 1
        [proposal] = PendingStore(world["tenant"]).list(conn, world["trip_id"])
        assert proposal["reason"] == FORECAST_REASON
    assert world["engine"].tick().notified == []


def test_unanswered_forecast_expires_and_does_not_change_the_plan(api):
    trip_id = _create(api)
    _watch(api).tick()
    [proposal] = _proposals(api, trip_id)
    with get_connection() as conn, conn.transaction():
        expired = PendingStore(api["tenant"]).expire(conn, now=proposal["expires_at"])
    assert len(expired) == 1 and _proposals(api, trip_id)[0]["status"] == "expired"
    assert _detail(api, trip_id)["version"] == 1
