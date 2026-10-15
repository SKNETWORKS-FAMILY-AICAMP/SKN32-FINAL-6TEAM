"""도로 선택의 실제 붙임 거리와 여행 판정 근거 전달을 확인한다."""
from datetime import datetime
from types import SimpleNamespace
from copy import deepcopy

import pytest

from app.domains.travel_ops.instances.mobility.engine.car import CarService
from app.domains.travel_ops.instances.mobility.engine.fold import _car_value
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, _Snap
from .test_graph_router import make_records, xy
from .test_car_turn_restrictions_v1 import arc, policy, rule


@pytest.mark.parametrize('dijkstra', [False, True])
def test_actual_alternative_start_snap_is_reported(monkeypatch, dijkstra):
    records = make_records()
    policy(records, [rule(records, (0, 1), (1, 1), (1, 2))])
    router = GraphRouter(records=records)
    router.force_dijkstra = dijkstra
    router.warm(('car',))
    def middle(code, distance):
        edge = code >> 1
        coords, cum, _ = router._geom(edge)
        point = tuple(.4*a+.6*b for a, b in zip(coords[0], coords[-1]))
        return _Snap(edge, .6*cum[-1], distance, point, (0, .6))
    closest = middle(arc(records, (0, 1), (1, 1)), 0.0)
    alternative = middle(arc(records, (1, 0), (1, 1)), 8.8)
    end = middle(arc(records, (1, 1), (1, 2)), 0.0)
    monkeypatch.setattr(router, '_snap_many', lambda profile, lng, lat:
                        [closest, alternative] if (lng, lat) == closest.pt else [end])
    path = router.route(closest.pt, end.pt)['paths'][0]
    assert path['points']['coordinates'][0] == list(alternative.pt)
    assert path['snap_m'] == [8.8, 0.0]
    assert path['quality']['access_max_m'] == 8.8
    selected = path['turn_restrictions']['snap_selection']
    assert selected['nearest_snap_m'] == [0.0, 0.0]
    assert selected['selected_candidate_ranks'] == [1, 0]
    assert selected['candidate_counts'] == [2, 1]
    assert selected['used_non_nearest'] == [True, False]
    assert selected['physical_access_verified'] is False


def test_direct_same_edge_keeps_selected_start_and_end():
    router = GraphRouter(records=policy(make_records()))
    a = (xy(0, 0)[0]+.0002, xy(0, 0)[1])
    b = (xy(0, 0)[0]+.0007, xy(0, 0)[1])
    path = router.route(a, b)['paths'][0]
    assert path['distance'] < 60
    assert path['turn_restrictions']['snap_selection']['selected_candidate_ranks'] == [0, 0]
    assert path['snap_m'] == [0.0, 0.0]


@pytest.mark.parametrize('with_turns', [False, True])
def test_car_summary_and_trip_evidence_keep_summary_without_geometry(with_turns):
    path = dict(points=dict(type='LineString', coordinates=[[127, 37], [127.01, 37]]), snap_m=[8.8, 0.0])
    if with_turns:
        path['turn_restrictions'] = dict(status='partial_static_motorcar', applied_relations=2487,
            source_relations=6258, complete_road_rules=False, arc_codes=[10, 12], search_cost_seconds=9.2,
            snap_selection=dict(candidate_counts=[2, 1], selected_candidate_ranks=[1, 0],
                used_non_nearest=[True, False], nearest_snap_m=[0.0, 0.0], physical_access_verified=False))
    route = dict(paths=[path]) if with_turns else {}
    computed = dict(coverage_pct=dict(default=0, **{'class': 0}), distance_m=100, topis_time_s=12,
        gh_time_s=9.2, depart='03:00', arrive='03:01', day_type='평일', hour_start=3,
        coverage_m={}, n_edges=2, links=[], n_links=0)
    graph = SimpleNamespace(compute=lambda *args, **kwargs: deepcopy(computed))
    router = SimpleNamespace(route=lambda *args, **kwargs: route)
    rules = dict(car=dict(coverage={key: dict(value=50) for key in
        ('warn_class_pct', 'warn_default_pct', 'unknown_default_pct')}), taxi=dict(fare={}, planning_budget={}))
    summary = CarService(graph, router, rules).leg((127, 37), (127.01, 37), datetime(2026, 10, 9, 3))
    value = _car_value(summary, '서울_이동', 180, 181, [], dict(timetable_built_at='controlled', rules_version='test'))
    if not with_turns:
        assert 'routing_evidence' not in summary and 'routing_evidence' not in value
        return
    evidence = value['routing_evidence']
    assert evidence['snap_m'] == [8.8, 0.0]
    assert evidence['snap_selection']['used_non_nearest'] == [True, False]
    assert evidence['turn_restrictions']['applied_relations'] == 2487
    assert evidence['turn_restrictions']['complete_road_rules'] is False
    assert 'arc_codes' not in evidence['turn_restrictions']
    assert 'points' not in evidence and 'coordinates' not in evidence
    path['snap_m'][0] = 0
    path['turn_restrictions']['snap_selection']['used_non_nearest'][0] = False
    assert evidence['snap_m'] == [8.8, 0.0]
    assert evidence['snap_selection']['used_non_nearest'] == [True, False]
