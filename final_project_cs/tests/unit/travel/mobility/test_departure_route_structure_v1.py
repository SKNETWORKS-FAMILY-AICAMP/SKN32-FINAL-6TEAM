"""손상 저장 경로는 조회 전에 보류하고 다음 정상 안내는 계속 처리한다."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_departure_observer_v1 import NOW, scene, call, prediction
from ..test_departure_observer_notice_v1 import NoEvents, scene as notice_scene


@pytest.mark.parametrize('malformed', [
    {'mode': 'bus'}, 'bus', 1, [None], ['bus'], [{} , None],
])
def test_invalid_saved_route_shape_is_held_before_source_or_verifier(malformed):
    runtime, context = scene()
    option = context['options']['p']
    option['legs'] = deepcopy(malformed)
    option['check']['legs'] = deepcopy(malformed)
    before = deepcopy(context)
    runtime.verify_case = lambda *a, **kw: pytest.fail('손상 경로 판정 금지')
    got = call(runtime, context,
               bus_arrival=lambda *a, **kw: pytest.fail('손상 경로의 도착정보 조회 금지'))
    assert got['status'] == 'needs_replan'
    assert got['reason'] == 'route_check_missing_or_changed'
    assert got['observations'] == []
    assert context == before


def test_invalid_later_leg_cannot_query_the_valid_first_boarding():
    runtime, context = scene()
    for key in ('legs',):
        context['options']['p'][key].append(None)
        context['options']['p']['check'][key].append(None)
    got = call(runtime, context,
               bus_arrival=lambda *a, **kw: pytest.fail('뒷구간 손상 경로 조회 금지'))
    assert got['status'] == 'needs_replan'
    assert got['reason'] == 'route_check_missing_or_changed'


def test_broken_route_notice_is_held_and_next_valid_realtime_notice_recovers():
    runtime, context = scene()
    broken = deepcopy(context)
    broken['options']['p']['legs'] = [None]
    broken['options']['p']['check']['legs'] = [None]
    move, items = notice_scene()
    queries = []
    def source(*a, **kw):
        queries.append(1)
        return prediction(*a, **kw)
    for saved, expected in ((broken, 'held'), (context, 'ok')):
        status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
            now=NOW, departure_observer=lambda *a, **kw: call(runtime, saved, bus_arrival=source))
        assert status == expected
        assert (phrase is None) == (expected == 'held')
    assert len(queries) == 1
    assert '현재 버스 대기 반영' in phrase.render()


def test_valid_current_first_boarding_and_following_bus_are_still_recalculated():
    from types import SimpleNamespace
    from app.domains.travel_ops.instances.mobility.engine.bus_identity import bus_leg
    from .test_bus_stop_identity_v1 import world

    runtime, context = scene()
    _, route, rows = world()
    legs = [bus_leg(route, rows[4], rows[5]), bus_leg(route, rows[5], rows[7])]
    context['options']['p']['legs'] = legs
    context['options']['p']['check']['legs'] = deepcopy(legs)
    queries = []
    def walk(rid, stops, start, end, depart, day, q, minimum, old):
        queries.append((start, depart))
        return SimpleNamespace(minutes=12 if start == 5 else 4, complete=True,
                               used=end-start, half=0, fb=0, total=end-start, edge=False)
    runtime._v.bus_prof = SimpleNamespace(walk=walk, source_id='fixture/profile', dates=[20261008])
    got = call(runtime, context, bus_arrival=prediction)
    assert got['status'] == 'realtime'
    assert len(got['boarding_steps']) == 2
    assert got['boarding_steps'][0]['board_at'].endswith('10:07:00+09:00')
    assert got['boarding_steps'][1]['boarding_basis'] == 'timetable_model'
    assert all(depart >= 624 for start, depart in queries if start == 6)
