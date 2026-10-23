"""출발 관측은 현재 승차만 바꾸고 이후 구간은 바뀐 시각으로 다시 계산한다."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.bus_identity import bus_leg
from app.domains.travel_ops.instances.mobility.engine.guardrails import resolve
from app.domains.travel_ops.instances.mobility.engine.paths import RULES_DIR
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
from app.domains.travel_ops.instances.mobility.engine.verify_time import Timetable, Verifier
from .test_bus_stop_identity_v1 import world

NOW = datetime.fromisoformat('2026-10-09T10:00:00+09:00')
ORIGIN = {'lat': 37.505, 'lon': 127.0}
DESTINATION = {'lat': 37.508, 'lon': 127.0}


def scene():
    bus, route, rows = world()
    rules = resolve(json.loads((RULES_DIR / 'rules_v0.3.json').read_text(encoding='utf-8')))
    verifier = Verifier(Timetable(), None, rules, set(), bus=bus)
    verifier.bus_speed = lambda *args: (60, '시험 고정 속도', '추정', [])
    verifier.lfd_enabled = False
    runtime = Runtime(verifier, timetable_built_at='fixture-a', rules_version=rules['rules_version'], stats={})
    legs = [bus_leg(route, rows[4], rows[7])]
    context = {'schema_version': 1, 'timing_unit': 'model_minutes', 'from_place': ORIGIN,
               'to_place': DESTINATION, 'basis': {'timetable_built_at': 'fixture-a',
               'rules_version': runtime.rules_version}, 'party': {}, 'first_visit': False,
               'options': {'p': {'option_id': 'p', 'legs': legs, 'check': {'legs': deepcopy(legs),
                   'walk_place_in': 4, 'walk_stop_in': 2, 'walk_stop_out': 1, 'walk_place_out': 1}}}}
    return runtime, context


def call(runtime, context, **kwargs):
    return observe(runtime, context, 'p', now=NOW, deadline=NOW + timedelta(hours=1),
                   origin=ORIGIN, destination=DESTINATION, **kwargs)


def prediction(*args, stop_id, stop_sequence, now, ready_at):
    return {'status': 'predicted', 'source': 'fixture/arrival', 'route_id': args[0],
            'stop_id': stop_id, 'stop_sequence': stop_sequence, 'confirmed_at': now.isoformat(),
            'arrival_at': (now + timedelta(minutes=7)).isoformat()}


def test_current_boarding_ride_profile_and_egress_replace_the_saved_total():
    runtime, context = scene()
    queries = []
    def walk(rid, stops, start, end, depart, day, q, minimum, old):
        queries.append((start, end, depart, q))
        # 10:07에 타면 혼잡 시간대로 넘어간다. 대기만 바꾸면 3분을 잘못 유지한다.
        return SimpleNamespace(minutes=12 if depart >= 607 else 3, complete=True,
                               used=3, half=0, fb=0, total=3, edge=False)
    runtime._v.bus_prof = SimpleNamespace(walk=walk, source_id='fixture/profile', dates=[20261008])
    old = deepcopy(context)
    got = call(runtime, context, bus_arrival=prediction)
    assert got['status'] == 'realtime', got
    assert got['eta_min'] == 21 and got['arrival_at'].endswith('10:21:00+09:00')
    assert got['leg_results'][0]['wait_min'] == 1
    assert got['leg_results'][0]['ride_min'] == 12
    assert {(a, b) for a, b, _, _ in queries} == {(5, 8)}
    assert {dep for _, _, dep, _ in queries} == {607}
    assert context == old and not hasattr(runtime._v, '_bus_departures')


@pytest.mark.parametrize('status', ['stale', 'unavailable', 'no_boardable_prediction'])
def test_source_failure_revalidates_the_model_with_explicit_status(status):
    runtime, context = scene()
    got = call(runtime, context, bus_arrival=lambda *a, **kw: {'status': status})
    assert got['status'] == 'model_revalidated' and got['observations'][0]['status'] == status
    assert got['leg_results'][0]['wait_min'] == 5


@pytest.mark.parametrize('mutation,reason', [
    ('basis', 'basis_changed'), ('coords', 'place_changed'), ('legs', 'route_check_missing_or_changed'),
    ('access', 'access_context_invalid'), ('option', 'option_changed'),
])
def test_changed_context_does_not_query_an_unrelated_bus(mutation, reason):
    runtime, context = scene()
    if mutation == 'basis':
        context['basis']['rules_version'] = 'old'
    elif mutation == 'coords':
        context['from_place'] = dict(ORIGIN, lat=37.6)
    elif mutation == 'legs':
        context['options']['p']['check']['legs'] = []
    elif mutation == 'access':
        context['options']['p']['check']['walk_stop_in'] = float('nan')
    else:
        context['options']['p']['option_id'] = 'other'
    got = call(runtime, context, bus_arrival=lambda *a, **kw: pytest.fail('조회하면 안 됨'))
    assert got['status'] == 'needs_replan' and got['reason'] == reason


@pytest.mark.parametrize('field,value', [('stop_sequence', 1), ('route_id', 'other'),
    ('arrival_at', '2026-10-09T10:03:00+09:00'), ('confirmed_at', '2026-10-09T10:01:00+09:00')])
def test_mismatched_identity_or_clock_cannot_be_used(field, value):
    runtime, context = scene()
    def bad(*a, **kw):
        return dict(prediction(*a, **kw), **{field: value})
    assert call(runtime, context, bus_arrival=bad)['status'] == 'fatal'


def test_late_current_bus_does_not_produce_old_departure_guidance():
    runtime, context = scene()
    def delayed(*a, **kw):
        return dict(prediction(*a, **kw), arrival_at=(NOW + timedelta(minutes=58)).isoformat())
    assert call(runtime, context, bus_arrival=delayed)['status'] == 'needs_replan'


def test_future_bus_after_rail_is_not_replaced_with_current_bus_prediction():
    runtime, context = scene()
    leg = {'mode': 'subway', 'line': '2호선', 'from': 'A', 'to': 'B'}
    context['options']['p']['legs'].insert(0, leg)
    context['options']['p']['check']['legs'].insert(0, deepcopy(leg))
    captured = {}
    def verify(case, **kw):
        captured.update(case=case, overrides=kw)
        return SimpleNamespace(verdict='feasible', code=None, reason='fixture', legs=[],
                               arrive_min=630, arrive_worst_min=632)
    runtime.verify_case = verify
    got = call(runtime, context, bus_arrival=lambda *a, **kw: pytest.fail('미래 버스 조회 금지'))
    assert got['status'] == 'model_revalidated'
    assert captured['case']['depart_at'] == 606 and captured['overrides']['bus_departures'] == {}


def test_midnight_and_second_rounding_use_current_service_day():
    runtime, context = scene()
    captured = {}
    def verify(case, **kw):
        captured.update(case)
        return SimpleNamespace(verdict='feasible', code=None, reason='fixture', legs=[],
                               arrive_min=1470, arrive_worst_min=1472)
    runtime.verify_case = verify
    got = observe(runtime, context, 'p', now=datetime.fromisoformat('2026-10-10T00:00:01+09:00'),
                  deadline=datetime.fromisoformat('2026-10-10T01:00:00+09:00'),
                  origin=ORIGIN, destination=DESTINATION)
    assert captured['date'] == '2026-10-09' and captured['depart_at'] == 1447
    assert got['departure_at'] == '2026-10-10T00:01:00+09:00' and got['eta_min'] == 32


def test_live_departure_is_request_private_and_not_reused_for_departure_search(monkeypatch):
    runtime, context = scene()
    runtime._v.lfd_enabled = True
    seen = []
    def search(self, *a):
        seen.append(self.lfd_enabled)
        assert not self.lfd_enabled
        return None
    monkeypatch.setattr(Verifier, '_last_feasible_depart', search)
    assert call(runtime, context, bus_arrival=prediction)['status'] == 'realtime'
    assert seen and runtime._v.lfd_enabled and not hasattr(runtime._v, '_bus_departures')


def test_later_bus_is_recomputed_after_first_ride_and_transfer_not_given_current_eta():
    runtime, context = scene()
    bus, route, rows = world()
    legs = [bus_leg(route, rows[4], rows[5]), bus_leg(route, rows[5], rows[7])]
    context['options']['p']['legs'] = legs
    context['options']['p']['check']['legs'] = deepcopy(legs)
    calls, queries = [], []
    def source(*a, **kw):
        calls.append((a, kw))
        return prediction(*a, **kw)
    def walk(rid, stops, start, end, depart, day, q, minimum, old):
        queries.append((start, end, depart, q))
        return SimpleNamespace(minutes=12 if start == 5 else 4, complete=True,
                               used=end-start, half=0, fb=0, total=end-start, edge=False)
    runtime._v.bus_prof = SimpleNamespace(walk=walk, source_id='fixture/profile', dates=[20261008])
    got = call(runtime, context, bus_arrival=source)
    assert got['status'] == 'realtime', got
    assert len(calls) == 1 and calls[0][1]['stop_sequence'] == 5
    vehicle = [leg for leg in got['leg_results'] if leg['ride_src']]
    assert vehicle[0]['depart_min'] == 607 and vehicle[0]['arrive_min'] == 619
    assert vehicle[1]['depart_min'] >= 624 and vehicle[1]['ride_min'] == 4
    assert all(dep >= 624 for start, end, dep, q in queries if start == 6)


def test_client_case_cannot_inject_realtime_departure():
    runtime, context = scene()
    case = {'id': 'fixture', 'date': '2026-10-09', 'stage': 'pre_departure',
            'depart_at': 606, 'arrive_by': 658, 'party': {}, 'first_visit': False,
            'legs': context['options']['p']['legs'], 'no_alternatives': True,
            'bus_departures': {'depart_min': 607}}
    got = runtime.verify_case(case)
    assert got.legs[0].depart_min == 611 and got.legs[0].wait_min == 5
