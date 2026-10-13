"""회전 자료가 없는 차량 경로도 실제 선택 도로를 표시해야 한다."""
import pytest

from app.domains.travel_ops.instances.mobility.engine.car import hav
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, _Snap
from .test_graph_router import encode_polyline


def parallel_roads():
    points = [(127, 37.5), (127, 37.501), (127, 37.502),
              (127.0001, 37.5), (127.0001, 37.501), (127.0001, 37.502)]
    nodes = [dict(id=i, lon=point[0], lat=point[1], r=1) for i, point in enumerate(points)]
    edges = []
    for u, v, speed in ((0, 1, 5), (1, 2, 5), (3, 4, 40), (4, 5, 40), (1, 4, 30)):
        geometry = [points[u], points[v]]
        edges.append(dict(u=u, v=v, way=len(edges)+1, sa=0, sb=1,
                          len=hav(*geometry), ow=0, hw='residential', ms=speed,
                          car=1, bike=1, bow=0, main=1, bmain=1,
                          g=encode_polyline(geometry)))
    return dict(nodes=nodes, edges=edges)


@pytest.mark.parametrize('dijkstra', [False, True])
@pytest.mark.parametrize('direct', [False, True])
def test_no_turn_sidecar_reports_actual_parallel_road_choice(monkeypatch, dijkstra, direct):
    router = GraphRouter(records=parallel_roads())
    router.force_dijkstra = dijkstra
    router.warm(('car',))
    start = (127, 37.5004)
    end = (127, 37.5008 if direct else 37.5016)

    def snap(edge, fraction, requested):
        coords, cum, _ = router._geom(edge)
        point = tuple((1-fraction)*a+fraction*b for a, b in zip(coords[0], coords[-1]))
        return _Snap(edge, fraction*cum[-1], hav(requested, point), point, (0, fraction))

    starts = [snap(0, .4, start), snap(2, .4, start)]
    ends = [snap(0 if direct else 1, .8 if direct else .6, end),
            snap(2 if direct else 3, .8 if direct else .6, end)]
    monkeypatch.setattr(router, '_snap_many', lambda profile, lng, lat:
                        starts if (lng, lat) == start else ends)
    path = router.route(start, end)['paths'][0]
    assert path['points']['coordinates'][0] == list(starts[1].pt)
    assert path['points']['coordinates'][-1] == list(ends[1].pt)
    actual_distances = [round(starts[1].dist, 1), round(ends[1].dist, 1)]
    assert actual_distances == [8.8, 8.8]
    assert path['snap_m'] == actual_distances
    assert path['quality']['access_max_m'] == 8.8
    turns = path['turn_restrictions']
    assert turns['status'] == 'unavailable' and turns['applied_relations'] == 0
    assert turns['complete_road_rules'] is False
    assert turns['snap_selection']['selected_candidate_ranks'] == [1, 1]
    assert turns['snap_selection']['used_non_nearest'] == [True, True]
    assert turns['snap_selection']['nearest_snap_m'] == [0.0, 0.0]
