"""손상 접근 시간이 현재 조회·안내 회차를 중단하지 않는지 검증한다."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from app.domains.travel_ops.instances.mobility.engine.timeutil import SERVICE_DAY_MAX_MIN
from .test_departure_observer_v1 import NOW, scene, call, prediction
from ..test_departure_observer_notice_v1 import NoEvents, scene as notice_scene


FIELDS = ('walk_place_in', 'walk_stop_in', 'walk_stop_out', 'walk_place_out')


@pytest.mark.parametrize('field', FIELDS)
@pytest.mark.parametrize('value', [1e30, 10**1000, SERVICE_DAY_MAX_MIN+0.1,
                                  float('inf'), float('nan'), -1, True])
def test_corrupt_access_is_rejected_before_current_source_or_verifier(field, value):
    runtime, context = scene()
    context['options']['p']['check'][field] = value
    before = deepcopy(context)
    runtime.verify_case = lambda *a, **k: pytest.fail('잘못된 접근값으로 판정하면 안 됨')
    got = call(runtime, context,
               bus_arrival=lambda *a, **k: pytest.fail('잘못된 접근값으로 API 조회하면 안 됨'))
    assert got['status'] == 'needs_replan' and got['reason'] == 'access_context_invalid'
    assert got['observations'] == []
    assert context['options']['p']['check'].keys() == before['options']['p']['check'].keys()
    for key in FIELDS:
        assert repr(context['options']['p']['check'][key]) == repr(before['options']['p']['check'][key])


@pytest.mark.parametrize('fields', [FIELDS[:2], FIELDS[2:]])
def test_combined_duration_cannot_escape_horizon(fields):
    runtime, context = scene()
    for field in fields:
        context['options']['p']['check'][field] = SERVICE_DAY_MAX_MIN/2+0.1
    got = call(runtime, context, bus_arrival=lambda *a, **k: pytest.fail('API 조회 금지'))
    assert got['status'] == 'needs_replan' and got['reason'] == 'access_context_invalid'


@pytest.mark.parametrize('field', (FIELDS[0], FIELDS[2]))
@pytest.mark.parametrize('value', [SERVICE_DAY_MAX_MIN, float(SERVICE_DAY_MAX_MIN)])
def test_exact_duration_boundary_is_valid_but_misses_this_deadline(field, value):
    runtime, context = scene()
    context['options']['p']['check'].update(dict.fromkeys(FIELDS, 0))
    context['options']['p']['check'][field] = value
    got = call(runtime, context, bus_arrival=lambda *a, **k: pytest.fail('기한 밖 조회 금지'))
    assert got['status'] == 'needs_replan' and got['reason'] == 'deadline_outside_service_horizon'


@pytest.mark.parametrize('excess,reason', [(0, 'deadline_outside_service_horizon'),
                                         (0.0000001, 'access_context_invalid')])
def test_exact_sum_boundary_is_distinct_from_a_corrupt_sum(excess, reason):
    runtime, context = scene()
    context['options']['p']['check'].update(dict.fromkeys(FIELDS, 0))
    context['options']['p']['check']['walk_place_in'] = SERVICE_DAY_MAX_MIN/2
    context['options']['p']['check']['walk_stop_in'] = SERVICE_DAY_MAX_MIN/2+excess
    got = call(runtime, context, bus_arrival=lambda *a, **k: pytest.fail('기한 밖 조회 금지'))
    assert got['status'] == 'needs_replan' and got['reason'] == reason


@pytest.mark.parametrize('field', FIELDS)
def test_missing_access_field_is_not_replaced_with_zero(field):
    runtime, context = scene()
    del context['options']['p']['check'][field]
    got = call(runtime, context, bus_arrival=lambda *a, **k: pytest.fail('접근값 누락 조회 금지'))
    assert got['status'] == 'needs_replan' and got['reason'] == 'access_context_invalid'


@pytest.mark.parametrize('values', [(0, 0, 0, 0), (4.25, 1.25, 0.25, 1.25)])
def test_valid_zero_and_fractional_durations_keep_current_boarding(values):
    runtime, context = scene()
    context['options']['p']['check'].update(dict(zip(FIELDS, values)))
    before = deepcopy(context)
    got = call(runtime, context, bus_arrival=prediction)
    assert got['status'] == 'realtime' and got['leg_results'][0]['depart_min'] == 607
    assert got['boarding_steps'][0]['board_at'] == '2026-10-09T10:07:00+09:00'
    assert context == before


def test_bad_notice_can_be_held_then_next_valid_notice_is_built():
    runtime, context = scene()
    broken = deepcopy(context)
    broken['options']['p']['check']['walk_stop_in'] = 1e30
    move, items = notice_scene()
    queries = []
    def source(*a, **kw):
        queries.append(1)
        return prediction(*a, **kw)
    for saved, expected in [(broken, 'held'), (context, 'ok')]:
        status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
            now=NOW, departure_observer=lambda *a, **kw: call(runtime, saved, bus_arrival=source))
        assert status == expected
        assert (phrase is None) == (expected == 'held')
    assert len(queries) == 1
    assert '현재 버스 대기 반영' in phrase.render()
