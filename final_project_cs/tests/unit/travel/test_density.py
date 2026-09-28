from datetime import datetime

import pytest

from app.modules.travel_ops.density import measure_density
from app.modules.travel_ops.itinerary_checks import Part, check_itinerary


def at(clock):
    return datetime.fromisoformat(f"2026-09-23T{clock}:00+09:00")


def part(seq=1, start="10:00", end="18:00", **kw):
    return Part(seq, "activity", "방문", at(start), at(end) if end else None, **kw)


def constraints(**window):
    return {"density": {"level": "normal", "days": {"2026-09-23": {
        "starts_at": at("10:00").isoformat(), "ends_at": at("22:00").isoformat(),
        "buffer_minutes": 0, **window}}}}


def test_excess_is_warning_not_violation():
    items = [part()]
    result = measure_density(items, constraints())
    day = result["density"][0]
    assert day["occupied_minutes"] == 480
    assert day["available_minutes"] == 720
    assert day["actual_density"] == pytest.approx(2 / 3)
    assert result["warnings"][0]["code"] == "density_exceeded"
    assert check_itinerary(items, constraints=constraints()) == []


def test_exact_threshold_and_buffer():
    assert measure_density([part(end="16:36")], constraints())["warnings"] == []
    assert measure_density([part(end="16:36")], constraints(buffer_minutes=1))["warnings"]


@pytest.mark.parametrize("items", [
    [part(end=None)],
    [part(end="23:00")],
    [part(end="09:00")],
    [part(end="12:00"), part(2, "11:00", "13:00")],
    [part(end="12:00"), part(2, "13:00", "14:00")],
    [part(start="09:00", end="12:00")],
])
def test_unknown_or_inconsistent_times_never_look_relaxed(items):
    day = measure_density(items, constraints())["density"][0]
    assert day["status"] == "unmeasurable"
    assert day["actual_density"] is None and day["occupied_minutes"] is None


def test_transfer_counted_once_and_same_place_needs_no_transfer():
    items = [part(end="12:00", place={"place_id": "a"}),
             part(2, "13:00", "14:00", place={"place_id": "b"}, detail={"transfer_minutes_before": 20})]
    assert measure_density(items, constraints(buffer_minutes=30))["density"][0]["occupied_minutes"] == 230
    items[1] = part(2, "13:00", "14:00", place={"place_id": "a"})
    assert measure_density(items, constraints())["density"][0]["occupied_minutes"] == 180


def test_mobility_allocated_time_includes_eta_and_buffer_not_added_twice():
    move = Part(2, "mobility", "이동", at("12:00"), at("13:00"), route={
        "planned": "bus", "options": [{"id": "bus", "eta_min": 40}]})
    items = [part(end="12:00"), move, part(3, "13:00", "14:00")]
    assert measure_density(items, constraints())["density"][0]["occupied_minutes"] == 240
    move.route["options"][0]["eta_min"] = None
    assert measure_density(items, constraints())["density"][0]["status"] == "unmeasurable"


@pytest.mark.parametrize("value", [None, {}, "normal", {"level": "bad", "days": {}},
    {"level": "normal", "days": {"bad": {}}}])
def test_invalid_input_is_explicit_warning(value):
    result = measure_density([part()], {"density": value})
    assert result["warnings"][0]["code"] == "density_unmeasurable"


def test_missing_configuration_is_opt_in():
    assert measure_density([part()], {}) == {"density": [], "warnings": []}


def test_offsets_and_overnight_window():
    config = constraints(ends_at="2026-09-24T02:00:00+09:00")
    item = Part(1, "activity", "야간", datetime.fromisoformat("2026-09-23T15:00:00+00:00"),
                datetime.fromisoformat("2026-09-23T16:00:00+00:00"))
    day = measure_density([item], config)["density"][0]
    assert day["date"] == "2026-09-23" and day["occupied_minutes"] == 60


def test_unknown_day_and_overlapping_windows():
    config = constraints()
    config["density"]["days"] = {"2026-09-22": {
        "starts_at": "2026-09-22T10:00:00+09:00", "ends_at": "2026-09-22T22:00:00+09:00", "buffer_minutes": 0}}
    assert measure_density([part()], config)["warnings"][0]["date"] == "2026-09-23"
    config = constraints(ends_at="2026-09-24T02:00:00+09:00")
    config["density"]["days"]["2026-09-24"] = {
        "starts_at": "2026-09-24T01:00:00+09:00", "ends_at": "2026-09-24T10:00:00+09:00", "buffer_minutes": 0}
    assert measure_density([part()], config)["density"][0]["status"] == "unmeasurable"


def test_explicit_target_is_preference_not_research_threshold():
    config = constraints()
    config["density"].pop("level")
    config["density"]["target_density"] = 0.75
    result = measure_density([part()], config)
    day = result["density"][0]
    assert day["target_density"] == 0.75 and day["policy_basis"] == "user_preference"
    assert result["warnings"] == []  # 8/12 exceeds the old normal preset, not this preference
    assert day["measurement_scope"] == "submitted_schedule"
    assert day["buffer_placement"] == "unallocated"
    assert day["policy_id"] and day["research_as_of"]


@pytest.mark.parametrize("target", [0, 1, -0.1, True, "0.7", float("inf"), float("nan")])
def test_invalid_explicit_targets_never_become_presets(target):
    config = constraints()
    config["density"].pop("level")
    config["density"]["target_density"] = target
    day = measure_density([part()], config)["density"][0]
    assert day["status"] == "unmeasurable" and day["target_density"] is None


def test_ambiguous_target_is_reported():
    config = constraints()
    config["density"]["target_density"] = 0.75
    assert measure_density([part()], config)["density"][0]["status"] == "unmeasurable"


def test_time_breakdown_counts_queue_once_and_marks_unknown_queues():
    items = [part(end="12:00", detail={"queue_minutes": 30}),
             Part(2, "mobility", "이동", at("12:00"), at("13:00"), route={
                 "planned": "bus", "options": [{"id": "bus", "eta_min": 40}]}),
             part(3, "13:00", "14:00")]
    day = measure_density(items, constraints(buffer_minutes=20))["density"][0]
    assert day["occupied_minutes"] == 260  # 240 scheduled + 20 buffer, queue is already inside
    assert day["breakdown"] == {
        "scheduled_minutes": 240, "transfer_minutes": 0, "buffer_minutes": 20,
        "evidence_buffer_minutes": 0.0,
        "travel_minutes": 60, "known_queue_minutes": 30,
        "queue_unannotated_items": 1, "unallocated_minutes": 460}


@pytest.mark.parametrize("queue", [-1, 481, None, True, "30", float("inf")])
def test_invalid_queue_cannot_create_false_precision(queue):
    day = measure_density([part(detail={"queue_minutes": queue})], constraints())["density"][0]
    assert day["status"] == "unmeasurable" and day["breakdown"] is None


def test_budget_deficit_is_visible_and_not_clamped_to_zero():
    day = measure_density([part()], constraints(buffer_minutes=300))["density"][0]
    assert day["status"] == "exceeded" and day["breakdown"]["unallocated_minutes"] == -60


def test_presets_and_direct_preferences_have_different_warning_basis():
    preset = measure_density([part()], constraints())["warnings"][0]
    config = constraints()
    config["density"].pop("level")
    config["density"]["target_density"] = 0.6
    explicit = measure_density([part()], config)["warnings"][0]
    assert preset["policy_basis"] == "research_calibrated" and "연구" in preset["reason"]
    assert explicit["policy_basis"] == "user_preference" and "사용자" in explicit["reason"]


def test_research_buffers_use_q95_mobility_rest_and_reservation_sources():
    move = Part(1, "mobility", "긴 이동", at("10:00"), at("11:00"), route={
        "planned": "bus", "options": [{"id": "bus", "eta_min": 40}],
        "average_eta_min": 40, "p95_eta_min": 52, "distance_m": 300})
    visit = part(2, "11:00", "12:00", detail={"reservation": True})
    config = constraints()
    config["mobility_ease"] = "needs_rest"
    config["first_visit"] = True
    day = measure_density([move, visit], config)["density"][0]
    # q95-average 12 + DfT 300/30*2 20 + first-visit 30 + reservation 30
    assert day["breakdown"]["evidence_buffer_minutes"] == 92
    assert day["occupied_minutes"] == 212


def test_rest_and_reservation_can_be_overridden_by_explicit_facility_values():
    visit = part(detail={"reservation": True, "arrival_buffer_minutes": 7})
    config = constraints()
    day = measure_density([visit], config)["density"][0]
    assert day["breakdown"]["evidence_buffer_minutes"] == 7
