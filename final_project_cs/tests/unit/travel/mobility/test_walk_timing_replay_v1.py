"""기록 경로를 다시 읽어도 계단 소요와 길 밖 접근 품질이 유지돼야 한다."""
from app.domains.travel_ops.instances.mobility.engine.bike import BikeRouter
from .test_walk_duration_contract_v1 import stair_router, planner_with_result
from .test_review_fixes_plan import PLACES


def test_recorded_foot_route_replays_same_distance_and_duration():
    records = {}
    live = BikeRouter(stair_router(), record=records)
    a, b = PLACES[:2]
    args = ('foot', a['lat'], a['lon'], b['lat'], b['lon'])
    actual = live.route(*args)
    replay = BikeRouter(fixture=records).route(*args)
    assert replay['foot_timing'] == actual['foot_timing']
    assert replay.get('quality') == actual.get('quality')
    assert replay.get('optimistic') == actual.get('optimistic')
    assert planner_with_result(replay)._walk_path(a, b, 280) == planner_with_result(actual)._walk_path(a, b, 280)
    replay['foot_timing']['seconds'] = 0
    assert next(iter(records.values()))['foot_timing']['seconds'] > 0


def test_old_fixture_without_internal_metadata_keeps_distance_contract():
    a, b = PLACES[:2]
    key = BikeRouter.key('foot', a['lat'], a['lon'], b['lat'], b['lon'])
    result = BikeRouter(fixture={key: {'distance_m': 300, 'time_s': 500}}).route(
        'foot', a['lat'], a['lon'], b['lat'], b['lon'])
    assert 'foot_timing' not in result
    planner = planner_with_result(result)
    assert planner._walk_path(a, b, 280) == (300, 300 / planner.speed / 60, False)
