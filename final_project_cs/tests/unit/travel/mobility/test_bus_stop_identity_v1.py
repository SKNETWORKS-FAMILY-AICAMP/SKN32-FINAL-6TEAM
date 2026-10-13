"""순환 노선의 동명 정류장이 원래 고른 행에서 바뀌지 않아야 한다."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.bus_identity import bus_leg, route_for_leg, segment_for_leg
from app.domains.travel_ops.instances.mobility.engine.paths import RULES_DIR
from app.domains.travel_ops.instances.mobility.engine.verify_time import Timetable, Verifier


def world():
    routes = [{'route_id': '100', 'route_nm': '순환1', 'route_type_nm': '간선',
               'first_time': '05:00', 'last_time': '23:00', 'term_min': 10, 'service_days': 'daily'}]
    names = {1: '승차', 2: '하차', 5: '승차', 8: '하차'}
    stops = [{'route_id': '100', 'seq': seq, 'station_nm': names.get(seq, f'중간{seq}'),
              'station_id': str(1000 + seq), 'sect_dist_m': 0 if seq == 1 else 1000,
              'lat': 37.5 + seq / 1000, 'lng': 127.0}
             for seq in range(1, 9)]
    bus = BusRoutes(routes, stops)
    return bus, bus.by_id['100'], stops


def test_selected_later_pair_does_not_become_the_shorter_same_name_pair():
    bus, route, rows = world()
    leg = bus_leg(route, rows[4], rows[7])
    assert bus.segment('100', '승차', '하차')[0]['seq'] == 1  # 종전 이름 입력
    a, b, span = segment_for_leg(bus, route_for_leg(bus, leg), leg)
    assert (a['seq'], b['seq'], span) == (5, 8, 3)
    assert (a['station_id'], b['station_id']) == ('1005', '1008')


@pytest.mark.parametrize('mutation', [
    {'from_stop_id': '1001'}, {'to_stop_id': '1002'}, {'from_sequence': None},
    {'to_sequence': 2}, {'from_sequence': True}, {'route_id': '999'}, {'route': '다른이름'},
])
def test_inconsistent_identity_is_rejected_instead_of_searching_by_name(mutation):
    bus, route, rows = world()
    leg = dict(bus_leg(route, rows[4], rows[7]), **mutation)
    assert segment_for_leg(bus, route, leg) is None


def test_partial_identity_does_not_fall_back_to_the_first_pair():
    bus, route, _ = world()
    leg = {'mode': 'bus', 'route': '순환1', 'from': '승차', 'to': '하차', 'route_id': '100'}
    assert segment_for_leg(bus, route, leg) is None


def test_legacy_name_input_keeps_existing_selection():
    bus, route, _ = world()
    leg = {'mode': 'bus', 'route': '순환1', 'from': '승차', 'to': '하차'}
    a, b, _ = segment_for_leg(bus, route_for_leg(bus, leg), leg)
    assert (a['seq'], b['seq']) == (1, 2)


def test_duplicate_sequence_is_not_silently_chosen():
    bus, route, rows = world()
    bus.stops['100'].append(dict(rows[4]))
    assert segment_for_leg(bus, route, bus_leg(route, rows[4], rows[7])) is None


def test_verifier_ride_and_transfer_positions_use_the_same_selected_rows():
    bus, route, rows = world()
    rules = json.loads((RULES_DIR / 'rules_v0.3.json').read_text(encoding='utf-8'))
    v = Verifier(Timetable(), None, rules, set(), bus=bus)
    v.bus_speed = lambda r, day: (60, '시험 고정 속도', '추정', [])
    leg = bus_leg(route, rows[4], rows[7])
    got = v.verify_leg_bus(0, leg, 600, 'weekday')
    assert got.verdict == 'feasible'
    assert got.ride_min == 3.0  # 3km를 시속60km로 이동: 종전 짧은 동명 구간은1분
    assert 'seq 5' in got.reason and 'seq 8' in got.reason
    assert v._bus_stop_row(leg, 'from')['seq'] == 5
    assert v._bus_stop_row(leg, 'to')['seq'] == 8
    invalid = dict(leg, from_stop_id='1001')
    assert v.verify_leg_bus(0, invalid, 600, 'weekday').code == 'no_data'
    assert v._bus_stop_row(invalid, 'from') is None


def test_fare_type_uses_selected_id_when_display_names_are_duplicated():
    from app.domains.travel_ops.instances.mobility.engine.options import bus_type
    bus, route, rows = world()
    other = replace(route, route_id='200', route_type_nm='광역')
    bus.by_id['200'] = other
    selected_rows = [dict(row, route_id='200') for row in rows]
    bus.stops['200'] = selected_rows
    leg = bus_leg(other, selected_rows[4], selected_rows[7])
    assert bus.route('순환1').route_type_nm == '간선'
    assert bus_type(SimpleNamespace(bus=bus), leg) == ('광역', 10)


def test_time_range_profile_uses_the_same_later_sequence_pair_as_the_verifier():
    from app.domains.travel_ops.instances.mobility.engine.plan_estimate import Estimator
    bus, route, rows = world()
    queries = []

    def walk(rid, stops, start, end, depart, day, quantile, minimum_days, old, **kw):
        queries.append((start, end))
        return SimpleNamespace(complete=True, minutes={'p10': 3, 'p50': 4, 'p90': 5}[quantile])

    v = SimpleNamespace(bus=bus, bus_prof=SimpleNamespace(walk=walk), rv=lambda *a: 1)
    estimator = SimpleNamespace(v=v, _dayf=lambda *a: ['weekday'])
    candidate = {'legs': [bus_leg(route, rows[4], rows[7])],
                 'legs_result': [SimpleNamespace(ride_src='profile', depart_min=600, ride_min=4)]}
    low, high, info = Estimator._bus_range(estimator, candidate, date(2026, 10, 9), 'weekday')
    assert (low, high) == (-1, 1) and queries == [(5, 8)] * 3
    assert (info['a']['seq'], info['b']['seq']) == (5, 8)
