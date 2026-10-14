"""지하철 소스→현재 승차→후속 구간→안내의 통제 연결 시험. 실탑승 아님."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace

import pytest
import httpx

from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.instances.mobility.engine.line_order import LineOrder
from app.domains.travel_ops.instances.mobility.engine.verify_time import Verifier, Timetable, Dep
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
from app.domains.travel_ops.instances.mobility.engine.subway_identity import SubwayStationIndex
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.guardrails import resolve
from app.domains.travel_ops.instances.mobility.engine.paths import RULES_DIR
from app.domains.travel_ops.instances.mobility.engine.transfer_walk import Walk
from app.domains.travel_ops.ports.data_sources.seoul_subway import select_boardable_arrival
from .test_departure_observer_v1 import NOW, ORIGIN, DESTINATION


def scene():
    names = ['양평', '영등포구청', '영등포시장']
    line = {'is_loop': False, 'stations': [{'station_nm': s} for s in names],
            'edges': [{'a': a, 'b': b, 'grade': '확정', 'travel_min': 3,
                       'travel_min_grade': '추정', 'dir_a_to_b': 'U', 'dir_b_to_a': 'D'}
                      for a, b in zip(names, names[1:])]}
    lo = LineOrder({'built_at': 'controlled/static', 'lines': {'05호선': line}})
    tt = Timetable()
    tt.fetched_at = 'controlled/timetable'
    for station in names:
        tt.stations.add(('05호선', station))
        tt.by_key[('05호선', station, 'holiday')] = [Dep(590, 'U', names[-1]), Dep(610, 'U', names[-1]), Dep(615, 'U', names[-1]), Dep(620, 'U', names[-1])]
    rules = resolve(json.loads((RULES_DIR / 'rules_v0.3.json').read_text(encoding='utf8')))
    verifier = Verifier(tt, lo, rules, {'2026-10-09'})
    verifier.tw = SimpleNamespace(lookup=lambda *a: Walk(3, '추정', 'pair', '통제 환승 시간', checked_at='controlled'))
    verifier.lfd_enabled = False
    rt = Runtime(verifier, timetable_built_at=tt.fetched_at, rules_version=rules['rules_version'], stats={})
    doc = {'schema_version': '1.0', 'station_count': 3, 'line_count': 1, 'stations': [
        {'line_id': '1005', 'station_id': f'1005000{522+i}', 'line': '5호선', 'station': s, 'query_station': s}
        for i, s in enumerate(names)]}
    rt.subway_stations = SubwayStationIndex(doc, content_sha256='a' * 64)
    leg = {'mode': 'subway', 'line': '05호선', 'from': names[0], 'to': names[1]}
    context = {'schema_version': 1, 'timing_unit': 'model_minutes', 'from_place': ORIGIN, 'to_place': DESTINATION,
               'basis': input_basis(rt), 'party': {}, 'first_visit': False,
               'options': {'p': {'option_id': 'p', 'legs': [leg], 'check': {'legs': [deepcopy(leg)],
                  'walk_place_in': 4, 'walk_stop_in': 2, 'walk_stop_out': 1, 'walk_place_out': 1},
                  'subway_identity': rt.subway_stations.bind(leg)}}}
    return rt, context


def source(station, **kw):
    assert station == '양평'
    services = kw['allowed_services']
    assert services
    path = max((s['path_station_ids'] for s in services), key=len)
    snapshot = {'kind': 'subway_arrival', 'source': 'controlled/subway', 'confirmed_at': kw['now'].isoformat(),
                'trains': [{'line_id': kw['line_id'], 'station_id': kw['station_id'], 'next_station_id': path[1],
                            'terminal_station_id': path[-1], 'train_number': '0501', 'train_status': '일반',
                            'eta_seconds': 480, 'eta_status': 'valid', 'arrival_code': '99', 'received_at': kw['now'].isoformat()}]}
    return select_boardable_arrival(snapshot, max_age_seconds=30, max_provider_age_seconds=90,
                                    max_provider_clock_ahead_seconds=2, **kw)


def call(rt, context, **kw):
    return observe(rt, context, 'p', now=NOW, deadline=NOW+timedelta(hours=1), origin=ORIGIN, destination=DESTINATION, **kw)


def test_selected_current_train_changes_first_boarding_and_eta_without_borrowing_run():
    rt, context = scene()
    original = deepcopy(context)
    got = call(rt, context, subway_arrival=source)
    assert got['status'] == 'realtime' and got['realtime_mode'] == 'subway', got
    assert got['eta_min'] == 13 and got['leg_results'][0]['depart_min'] == 608
    assert got['leg_results'][0]['ride_min'] == 3 and got['leg_results'][0]['ride_src'] == 'subway_path_model'
    assert context == original and not hasattr(rt._v, '_subway_departures')


def test_later_segment_is_recalculated_from_current_arrival_not_old_total():
    rt, context = scene()
    leg = {'mode': 'subway', 'line': '05호선', 'from': '영등포구청', 'to': '영등포시장'}
    context['options']['p']['legs'].append(leg)
    context['options']['p']['check']['legs'].append(deepcopy(leg))
    calls = []
    def current(*args, **kw):
        calls.append(args[0])
        return source(*args, **kw)
    got = call(rt, context, subway_arrival=current)
    assert got['status'] == 'realtime' and calls == ['양평'], got
    assert [x['depart_min'] for x in got['leg_results'] if x['depart_min'] is not None] == [608, 615]
    assert got['eta_min'] == 20


@pytest.mark.parametrize('status', ['unavailable', 'stale', 'no_boardable_prediction'])
def test_failure_explicitly_revalidates_model(status):
    rt, context = scene()
    got = call(rt, context, subway_arrival=lambda *a, **kw: {'status': status})
    assert got['status'] == 'model_revalidated' and got['observations'][0]['status'] == status
    assert got['leg_results'][0]['depart_min'] == 610


@pytest.mark.parametrize('field,value', [('line_id', '1002'), ('station_id', 'other'), ('target_station_id', 'other'),
    ('terminal_station_id', 'other'), ('path_station_ids', []), ('train_status', '급행'), ('train_number', None),
    ('arrival_at', (NOW+timedelta(minutes=1)).isoformat())])
def test_changed_source_identity_never_reaches_verifier(field, value):
    rt, context = scene()
    def bad(*a, **kw):
        return dict(source(*a, **kw), **{field: value})
    assert call(rt, context, subway_arrival=bad)['status'] == 'fatal'


def test_query_completion_recomputes_access_before_applying_prediction():
    rt, context = scene()
    def delayed(*a, **kw):
        result = source(*a, **kw)
        result['evaluated_at'] = (NOW+timedelta(seconds=61)).isoformat()
        return result
    got = call(rt, context, subway_arrival=delayed)
    assert got['status'] == 'realtime' and got['departure_at'].endswith('10:02:00+09:00')
    assert got['leg_results'][0]['wait_min'] == 0


def test_station_mapping_failure_is_visible_and_does_not_query():
    rt, context = scene()
    rt.subway_stations = None
    context['options']['p']['subway_identity'] = {'status': 'unavailable', 'reason': 'station_identity_source_missing'}
    got = call(rt, context, subway_arrival=lambda *a, **kw: pytest.fail('대응 불가 조회 금지'))
    assert got['status'] == 'model_revalidated' and got['observations'][0]['status'] == 'unavailable'


def test_loop_is_modelled_without_querying_current_ambiguous_direction():
    rt, context = scene()
    rt._v.lo.doc['lines']['05호선']['is_loop'] = True
    # 시간표 모델은 따로 통제하여, 이 시험이 확인하는 것은 현재 소스 조회 생략과 상태 보존이다.
    rt.verify_case = lambda *a, **kw: SimpleNamespace(verdict='feasible', code=None, reason='controlled', legs=[], arrive_min=615, arrive_worst_min=615)
    got = call(rt, context, subway_arrival=lambda *a, **kw: pytest.fail('순환선 조회 금지'))
    assert got['status'] == 'model_revalidated' and got['observations'][0]['reason'] == 'loop_realtime_not_supported'


def test_observed_train_cannot_cross_disruption():
    rt, context = scene()
    got = call(rt, context, subway_arrival=source, disruptions=[{'kind': 'edge_closed', 'line': '05호선',
              'between': ['양평', '영등포구청'], 'grade': '확정', 'source_id': 'controlled/closure'}])
    assert got['status'] == 'needs_replan'


def test_unrelated_express_runtime_is_not_reused_as_current_regular_ride():
    rt, context = scene()
    for d in rt._v.tt.by_key[('05호선', '양평', 'holiday')]:
        d.run = SimpleNamespace(express=False, serves=lambda *a: True, ride_min=lambda *a: 1)
    got = call(rt, context, subway_arrival=source)
    assert got['status'] == 'realtime' and got['leg_results'][0]['ride_min'] == 3


def test_invalid_empty_callback_has_failure_evidence():
    rt, context = scene()
    got = call(rt, context, subway_arrival=lambda *a, **kw: None)
    assert got['status'] == 'model_revalidated' and got['observations'][0]['reason'] == 'invalid_observation'


def test_query_consuming_deadline_never_emits_departure():
    rt, context = scene()
    def delayed(*a, **kw):
        return dict(source(*a, **kw), evaluated_at=(NOW+timedelta(hours=1)).isoformat())
    got = call(rt, context, subway_arrival=delayed)
    assert got['status'] == 'needs_replan' and got['reason'] == 'deadline_passed_during_query'


def test_future_subway_after_bus_is_not_queried_as_current():
    rt, context = scene()
    bus = {'mode': 'bus', 'route': '통제 노선', 'from': '승차', 'to': '하차'}
    context['options']['p']['legs'].insert(0, bus)
    context['options']['p']['check']['legs'].insert(0, deepcopy(bus))
    context['options']['p']['subway_identity'] = None
    rt.verify_case = lambda *a, **kw: SimpleNamespace(verdict='feasible', code=None, reason='controlled', legs=[], arrive_min=615, arrive_worst_min=615)
    got = call(rt, context, subway_arrival=lambda *a, **kw: pytest.fail('미래 지하철 조회 금지'))
    assert got['status'] == 'model_revalidated' and got['observations'] == []


def test_real_factory_hook_and_notice_display_subway_wait(monkeypatch):
    from app import composition
    from app.domains.travel_ops.instances.mobility import wiring
    from app.domains.travel_ops.components.watch.trip_reminders import build_departure
    from ..test_departure_assembly_v1 import setup, POLICY
    from ..test_departure_observer_notice_v1 import NoEvents
    rt, context = scene()
    _, move, items, _, _ = setup(monkeypatch)
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: rt)
    move.detail['departure_context'] = context
    move.detail['route_def']['options'][0].update(label='지하철', uses=['05호선'])
    calls = []
    class Arrival:
        def boardable_arrival(self, station, **kwargs):
            calls.append((station, deepcopy(kwargs)))
            for key in ('max_age_seconds', 'max_provider_age_seconds', 'max_provider_clock_ahead_seconds'):
                kwargs.pop(key)
            return source(station, **kwargs)
    policy = dict(POLICY, **{'travel.subway_arrival_cache_seconds': 30})
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='controlled'),
        SimpleNamespace(bus_arrival=None, subway_arrival=Arrival()), guardrails=policy)
    original = deepcopy(move)
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None, now=NOW, departure_observer=observer)
    text = phrase.render()
    assert status == 'ok' and '약 13분' in text and '현재 지하철 대기 반영' in text
    assert '현재 버스 대기 반영' not in text and move == original
    assert len(calls) == 1 and calls[0][1]['station_id'] == '1005000522'
    assert calls[0][1]['max_age_seconds'] == 30


@pytest.mark.parametrize('ttl', [0, -1, True, '30', float('inf'), 10**1000])
def test_subway_cache_policy_is_validated(ttl):
    from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
    with pytest.raises(ValueError): SeoulSubwayArrival(service_key='controlled-key', cache_ttl_seconds=ttl)


def test_existing_long_cache_entry_is_refreshed_under_short_policy():
    from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
    from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival, BASE, PAGE_SIZE
    cache = ResponseCache(ttl_seconds=300, clock=lambda: 0)
    calls = []
    def transport(url, params):
        calls.append(True)
        return httpx.Response(200, json={'realtimeArrivalList': []}, request=httpx.Request('GET', url))
    instance = SeoulSubwayArrival(service_key='controlled-key', cache=cache, cache_ttl_seconds=30, transport=transport)
    url = f'{BASE}/controlled-key/json/realtimeStationArrival/0/{PAGE_SIZE}/%EC%96%91%ED%8F%89'
    key = instance._cache_key(url, {})
    old = datetime.now(UTC) - timedelta(seconds=31)
    cache.put(key, {'realtimeArrivalList': []}, fetched_at=old, ttl_seconds=300)
    first = instance.arrivals('양평')
    second = instance.arrivals('양평')
    assert len(calls) == 1 and first['confirmed_at'] == second['confirmed_at']
    assert datetime.fromisoformat(first['confirmed_at']) > old


def test_crowding_future_wait_remains_model_and_does_not_make_worst_before_best():
    rt, context = scene()
    rt._v._congestion_hit = lambda *a: (110, '매우혼잡', {'source_id': 'controlled/crowd', 'fetched_at': NOW.isoformat()}, 'board_wait_extra_headway')
    got = call(rt, context, subway_arrival=source)
    assert got['status'] == 'realtime' and got['arrival_at'].endswith('10:13:00+09:00')
    assert datetime.fromisoformat(got['worst_arrival_at']) >= datetime.fromisoformat(got['arrival_at'])


def test_rail_to_rail_transfer_is_recalculated_after_current_boarding():
    rt, context = scene()
    # 실제 노선망 성능이 아니라 내부 환승 시각 연결을 통제한다.
    line = {'is_loop': False, 'stations': [{'station_nm': s} for s in ['영등포구청', '당산']],
            'edges': [{'a': '영등포구청', 'b': '당산', 'grade': '확정', 'travel_min': 3,
                       'travel_min_grade': '추정', 'dir_a_to_b': 'U', 'dir_b_to_a': 'D'}]}
    rt._v.lo = LineOrder({'built_at': 'controlled/static', 'lines': {'05호선': rt._v.lo.doc['lines']['05호선'], '02호선': line}})
    for name in ['영등포구청', '당산']:
        rt._v.tt.stations.add(('02호선', name))
        rt._v.tt.by_key[('02호선', name, 'holiday')] = [Dep(590, 'U', '당산'), Dep(620, 'U', '당산'), Dep(630, 'U', '당산')]
    rt._v.tw = SimpleNamespace(lookup=lambda *a: Walk(3, '추정', 'pair', '통제 환승 시간', checked_at='controlled'))
    leg = {'mode': 'subway', 'line': '02호선', 'from': '영등포구청', 'to': '당산'}
    context['options']['p']['legs'].append(leg)
    context['options']['p']['check']['legs'].append(deepcopy(leg))
    got = call(rt, context, subway_arrival=source)
    assert got['status'] == 'realtime', got
    assert got['leg_results'][0]['depart_min'] == 608
    assert got['leg_results'][-1]['depart_min'] == 620
    assert got['eta_min'] == 25


@pytest.mark.parametrize('crowded', [False, True])
def test_live_short_turn_uses_matching_ridden_segment_without_static_terminal_record(crowded):
    rt, context = scene()
    if crowded:
        rt._v._congestion_hit = lambda *a: (110, '매우혼잡', {'source_id': 'controlled/crowd', 'fetched_at': NOW.isoformat()}, 'board_wait_extra_headway')
    def short_turn(station, **kw):
        # 시간표에는 영등포시장행만 있지만 현재 응답은 목적지 영등포구청에서 종착한다.
        kw['allowed_services'] = [s for s in kw['allowed_services'] if s['path_station_ids'][-1] == kw['target_station_id']]
        return source(station, **kw)
    got = call(rt, context, subway_arrival=short_turn)
    assert got['status'] == 'realtime', got
    assert got['eta_min'] == 13 and got['leg_results'][0]['ride_src'] == 'subway_path_model'
    if crowded:
        assert got['worst_arrival_at'].endswith('10:15:00+09:00')
