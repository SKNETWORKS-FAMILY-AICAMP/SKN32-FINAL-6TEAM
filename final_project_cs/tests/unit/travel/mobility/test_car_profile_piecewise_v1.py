"""공개 도로 자료 계약을 재현한 통제 구간입니다. 실제 탑승시간을 입력하지 않습니다."""
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.mobility.engine.car import CarGraph, hav

KST = timezone(timedelta(hours=9))
THRESHOLD = 15.72


def graph(points, profiles, mapping):
    result = CarGraph.__new__(CarGraph)
    result.holidays = result.cal_hol = set()
    result.wayinfo = {1: ("primary", points)}
    result.seg = {1: mapping}
    result.prof = profiles
    result.cf = {"주간선도로": {"mean_kmh": {day: [30.0] * 24 for day in ("평일", "토요일", "휴일")}}}
    return result


def route(points):
    distance = sum(hav(a, b) for a, b in zip(points, points[1:]))
    return {"paths": [{"points": {"coordinates": points}, "details": {
        "osm_way_id": [[0, len(points) - 1, 1]], "road_class": [[0, len(points) - 1, "primary"]]},
        "distance": distance, "time": distance / 60 * 3.6 * 1000}]}


def reference(parts, departure, speed):
    """형상 추론과 독립적으로 알려진 노드쌍의 거리와 시간별 속도를 적분합니다."""
    now, slow_seconds, slow_distance = departure, 0.0, 0.0
    for remaining, link in parts:
        while remaining > 1e-8:
            kmh = speed(link, now)
            boundary = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            seconds = min(remaining / kmh * 3.6, (boundary - now).total_seconds())
            meters = seconds * kmh / 3.6
            if kmh < THRESHOLD:
                slow_seconds += seconds
                slow_distance += meters
            remaining -= meters
            now += timedelta(seconds=seconds)
    return {"topis_time_s": round((now - departure).total_seconds()),
            "slow_s": round(slow_seconds), "slow_m": round(slow_distance, 1)}


@pytest.mark.parametrize("reverse", [False, True])
def test_each_node_pair_uses_its_own_directional_link(reverse):
    points = [(127.0, 37.5), (127.001, 37.5), (127.002, 37.5)]
    profiles = {("first", "평일", 12): 60, ("second", "평일", 12): 6}
    mappings = {(index, direction): link for direction in ("fwd", "bwd")
                for index, link in enumerate(("first", "second"))}
    model = graph(points, profiles, mappings)
    departure = datetime(2026, 10, 12, 12, tzinfo=KST)
    parts = [(hav(points[0], points[1]), "first"), (hav(points[1], points[2]), "second")]
    if reverse:
        points, parts = list(reversed(points)), list(reversed(parts))
    got = model.compute(route(points), departure, slow_threshold_kmh=THRESHOLD)
    expected = reference(parts, departure, lambda link, at: profiles[(link, "평일", at.hour)])
    assert {name: got[name] for name in expected} == expected
    assert got["distance_m"] == round(sum(part[0] for part in parts), 1)
    assert {row["link_id"] for row in got["links"]} == {"first", "second"}


@pytest.mark.parametrize("before,after", [(60, 6), (6, 60), (60, 60)])
def test_time_and_low_speed_are_split_at_hour_even_inside_one_geometry_segment(before, after):
    points = [(127.0, 37.5), (127.012, 37.5)]
    departure = datetime(2026, 10, 12, 8, 59, 30, tzinfo=KST)
    profiles = {("link", "평일", 8): before, ("link", "평일", 9): after}
    model = graph(points, profiles, {(0, "fwd"): "link"})
    got = model.compute(route(points), departure, slow_threshold_kmh=THRESHOLD)
    expected = reference([(hav(*points), "link")], departure, lambda link, at: profiles[(link, "평일", at.hour)])
    assert {name: got[name] for name in expected} == expected
    assert got["coverage_pct"]["topis"] == 100.0
    assert got["n_edges"] == 1  # 시간대 분할은 형상 간선 수를 늘리지 않습니다.


def test_midnight_rechecks_date_daytype_and_hour():
    points = [(127.0, 37.5), (127.012, 37.5)]
    departure = datetime(2026, 10, 11, 23, 59, 30, tzinfo=KST)  # 일요일→월요일
    profiles = {("link", "휴일", 23): 60, ("link", "평일", 0): 6}
    model = graph(points, profiles, {(0, "fwd"): "link"})
    got = model.compute(route(points), departure, slow_threshold_kmh=THRESHOLD)
    expected = reference([(hav(*points), "link")], departure,
                         lambda link, at: profiles[(link, model.daytype(at), at.hour)])
    assert {name: got[name] for name in expected} == expected
    assert got["arrive"].startswith("2026-10-12T00:")


def test_missing_link_uses_time_varying_road_class_without_calling_it_topis():
    points = [(127.0, 37.5), (127.012, 37.5)]
    departure = datetime(2026, 10, 12, 8, 59, 30, tzinfo=KST)
    model = graph(points, {}, {})
    speeds = model.cf["주간선도로"]["mean_kmh"]["평일"]
    speeds[8], speeds[9] = 60, 6
    got = model.compute(route(points), departure, slow_threshold_kmh=THRESHOLD)
    expected = reference([(hav(*points), None)], departure, lambda _, at: speeds[at.hour])
    assert {name: got[name] for name in expected} == expected
    assert got["coverage_pct"] == {"topis": 0.0, "class": 100.0, "default": 0.0}
    assert got["links"] == []


def test_one_segment_crossing_multiple_hours_preserves_distance_and_low_speed_time():
    points = [(127.0, 37.5), (127.12, 37.5)]
    departure = datetime(2026, 10, 12, 8, 50, tzinfo=KST)
    profiles = {("link", "평일", hour): (6 if hour <= 9 else 60) for hour in range(24)}
    model = graph(points, profiles, {(0, "fwd"): "link"})
    got = model.compute(route(points), departure, slow_threshold_kmh=THRESHOLD)
    expected = reference([(hav(*points), "link")], departure, lambda link, at: profiles[(link, "평일", at.hour)])
    assert {name: got[name] for name in expected} == expected
    assert got["distance_m"] == round(hav(*points), 1)
    assert got["coverage_m"]["topis"] == round(hav(*points), 1)
