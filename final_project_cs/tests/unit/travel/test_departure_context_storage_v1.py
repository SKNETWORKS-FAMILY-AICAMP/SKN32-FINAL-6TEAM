"""구간 식별·모델 시각이 저장까지 유지되고 장소 변경 시 옛 문맥이 제거된다."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import json

import pytest

from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine.departure_context import capture
from app.domains.travel_ops.instances.mobility.engine.plan import core_routes
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange
from app.domains.travel_ops.components.planning.planner import add_moves
from .test_planner_engine_moves import PLACES, _items, _fake
from .test_moves_refresh_after_swap import _items as scene, _place, T


def test_context_copies_exact_selected_rows_and_keeps_model_units():
    leg = {"mode": "bus", "route": "순환", "route_id": "100", "from": "승", "to": "하",
           "from_stop_id": "101", "to_stop_id": "105", "from_sequence": 1, "to_sequence": 5}
    option = {"id": "bus_100", "eta_min": 21, "_start": 600, "_legs": [leg],
              "_check": {"legs": [leg], "walk_place_in": 6, "walk_place_out": 2},
              "_lr": [SimpleNamespace(idx=0, verdict="feasible", depart_min=609,
                                      arrive_min=619, wait_min=3, ride_min=10)]}
    context = capture([option], runtime=SimpleNamespace(timetable_built_at="version-a", rules_version="r1"),
                      origin=PLACES["P1"].as_place(), destination=PLACES["P2"].as_place(),
                      stage="planning", party={"adult": 2}, first_visit=True,
                      service_date=date(2026, 10, 7), start_min=600)
    recovered = json.loads(json.dumps(context))
    saved = recovered["options"]["bus_100"]
    assert saved["legs"][0]["to_sequence"] == 5
    assert saved["check"]["walk_place_in"] == 6
    assert saved["leg_results"][0]["wait_min"] == 3
    assert recovered["timing_unit"] == "model_minutes"
    option["_check"]["walk_place_in"] = 999
    leg["from_sequence"] = 99
    assert context["options"]["bus_100"]["legs"][0]["from_sequence"] == 1
    assert context["options"]["bus_100"]["check"]["walk_place_in"] == 6
    route = {"from": "A", "to": "B", "planned": "bus_100",
             "options": [{"id": "bus_100", "eta_min": 21, "uses": [], "_check": {"secret": 1}}]}
    assert set(core_routes({"r": route})["r"]["options"][0]) == {"id", "eta_min", "uses"}


def test_generated_move_stores_context_in_detail():
    context = {"schema_version": 1, "options": {"bus_1": {"legs": [{"route_id": "100"}]}}}
    route = {"planned": "bus_1", "options": [{"id": "bus_1", "eta_min": 9, "uses": []}]}
    engine = _fake(lambda arrival: {"route": route, "starts_at": arrival - timedelta(minutes=19),
                                   "ends_at": arrival - timedelta(minutes=10), "eta_min": 9,
                                   "departure_context": context})
    items, routes, _ = add_moves(_items(), PLACES, engine=engine)
    move = next(item for item in items if item["kind"] == "mobility")
    assert move["detail"]["departure_context"] == context
    assert "departure_context" not in routes[move["route"]]


@pytest.mark.parametrize("lat,lon", [(37.5755, 126.9855), (37.590, 127.000)])
def test_old_context_is_removed_when_new_place_cannot_be_rejudged(monkeypatch, lat, lon):
    monkeypatch.setattr(wiring, "leg_planner", lambda *args, **kwargs: None)
    act, move, meal = scene()
    move.detail["departure_context"] = {"from_place": {"name": "old"}}
    place = _place("새 식당", lat, lon)
    changed = meal.replaced_by(place=place, title="새 식당")
    changed.place = place
    change = ItineraryChange(reason="test", causes=[], notice={}, replacements={meal.item_id: changed})
    after = next(item for item in change.new_items([act, move, meal]) if item.kind == "mobility")
    assert "departure_context" not in after.detail
    assert "departure_context" in move.detail


def test_new_place_rejudgment_replaces_old_context(monkeypatch):
    from app.domains.travel_ops.components.team_hooks import legs

    act, move, meal = scene()
    move.detail["departure_context"] = {"old": True}
    new_context = {"schema_version": 1, "to_place": {"name": "새 식당"}, "options": {}}
    def builder(*args, **kwargs):
        def leg(a, b, arrival, floor):
            return {"route": {"planned": "walk", "options": [{"id": "walk", "eta_min": 9, "uses": []}]},
                    "starts_at": arrival - timedelta(minutes=19), "ends_at": arrival - timedelta(minutes=10),
                    "eta_min": 9, "departure_context": new_context}, None
        return leg
    # 일정 변경 부품이 읽는 끼움 위치에 대역을 넣는다. 조립 후 원본 함수 교체는 전달되지 않는다.
    monkeypatch.setattr(legs, "leg_planner", builder)
    place = _place("새 식당", 37.5755, 126.9855)
    changed = meal.replaced_by(place=place, title="새 식당")
    changed.place = place
    change = ItineraryChange(reason="test", causes=[], notice={}, replacements={meal.item_id: changed})
    after = next(item for item in change.new_items([act, move, meal]) if item.kind == "mobility")
    assert after.detail["departure_context"] == new_context


def test_actual_mini_engine_preserves_all_listed_options_in_generated_detail(tmp_path, monkeypatch):
    from app.domains.travel_ops.instances.mobility.engine import paths, runtime
    from .mobility.test_review_fixes_runtime import _write_mini_data
    before, state = (paths.SOURCE, paths.DATA_DIR), dict(wiring._STATE)
    monkeypatch.setattr(runtime, "_SINGLETON", None)
    try:
        _write_mini_data(tmp_path)
        wiring.configure(data_dir=str(tmp_path), gh_url="", seoul_key="")
        engine = wiring.leg_planner(2, {})
        got, reason = engine(PLACES["P1"].as_place(), PLACES["P2"].as_place(),
                             datetime(2026, 10, 7, 11, 0, tzinfo=timezone(timedelta(hours=9))), T("09:30"))
        assert got is not None, reason
        context = json.loads(json.dumps(got["departure_context"]))
        assert set(context["options"]) == {o["id"] for o in got["route"]["options"]}
        selected = context["options"][got["route"]["planned"]]
        assert selected["eta_min"] == got["eta_min"]
        assert selected["check"]["legs"] == selected["legs"]
        assert selected["leg_results"]
    finally:
        paths._layout(before[1], before[0])
        wiring._STATE.clear()
        wiring._STATE.update(state)
        runtime._SINGLETON = None
