"""운행일은 초 단위 원시 시각에서 정하고, 출발 분만 보수적으로 올린다."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.timeutil import day_type_of, to_service_min
from .test_departure_observer_v1 import DESTINATION, ORIGIN, scene


@pytest.mark.parametrize('clock,access,expected_date,expected_minute', [
    ('2026-10-10T03:59:01+09:00', 0, '2026-10-09', 1680),
    ('2026-10-10T03:53:01+09:00', 6, '2026-10-09', 1680),
    ('2026-10-10T03:59:59+09:00', 0, '2026-10-09', 1680),
    ('2026-10-10T04:00:00+09:00', 0, '2026-10-10', 240),
    ('2026-10-10T04:00:01+09:00', 0, '2026-10-10', 241),
    ('2026-10-09T23:59:01+09:00', 0, '2026-10-09', 1440),
    ('2026-10-12T03:59:01+09:00', 0, '2026-10-11', 1680),
    ('2026-10-09T18:59:01+00:00', 0, '2026-10-09', 1680),
])
def test_departure_preserves_service_day_before_rounding(clock, access, expected_date, expected_minute):
    runtime, context = scene()
    check = context['options']['p']['check']
    check.update(walk_place_in=access, walk_stop_in=0, walk_stop_out=0, walk_place_out=0)
    captured = {}
    def verify(case, **kwargs):
        captured.update(case)
        return SimpleNamespace(verdict='feasible', code=None, reason='controlled', legs=[],
                               arrive_min=case['depart_at'] + 10, arrive_worst_min=case['depart_at'] + 10)
    runtime.verify_case = verify
    now = datetime.fromisoformat(clock)
    got = observe(runtime, context, 'p', now=now, deadline=now + timedelta(hours=1),
                  origin=ORIGIN, destination=DESTINATION)
    assert got['status'] == 'model_revalidated', got
    assert captured['date'] == expected_date
    assert captured['depart_at'] == expected_minute
    local_ready = (now.astimezone(datetime.fromisoformat('2026-01-01T00:00:00+09:00').tzinfo)
                   + timedelta(minutes=access))
    assert captured['depart_at'] == to_service_min(local_ready.strftime('%H:%M:%S'), ceil_seconds=True)
    assert datetime.fromisoformat(got['arrival_at']) - now >= timedelta(minutes=10 + access)
    assert day_type_of(datetime.fromisoformat(captured['date']).date(), set()) == (
        'weekday' if expected_date == '2026-10-09' else 'holiday')


@pytest.mark.parametrize('completed,expected_date,expected_minute', [
    ('2026-10-10T03:59:01+09:00', '2026-10-09', 1680),
    ('2026-10-10T04:00:01+09:00', '2026-10-10', 241),
])
def test_query_completion_uses_same_unrounded_service_day(completed, expected_date, expected_minute):
    runtime, context = scene()
    context['options']['p']['check'].update(walk_place_in=0, walk_stop_in=0,
                                          walk_stop_out=0, walk_place_out=0)
    captured = {}
    def verify(case, **kwargs):
        captured.update(case)
        return SimpleNamespace(verdict='feasible', code=None, reason='controlled', legs=[],
                               arrive_min=case['depart_at']+10, arrive_worst_min=case['depart_at']+10)
    runtime.verify_case = verify
    now = datetime.fromisoformat('2026-10-10T03:58:00+09:00')
    got = observe(runtime, context, 'p', now=now, deadline=now+timedelta(hours=1),
                  origin=ORIGIN, destination=DESTINATION,
                  bus_arrival=lambda *a, **kw: {'status': 'unavailable', 'evaluated_at': completed})
    assert got['status'] == 'model_revalidated', got
    assert (captured['date'], captured['depart_at']) == (expected_date, expected_minute)
