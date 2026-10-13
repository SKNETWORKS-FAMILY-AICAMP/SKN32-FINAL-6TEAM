"""접수 계산 → 내부 검사 → 등록 지도에 같은 선택 경로를 전달한다."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import moves, review, registered_moves
from app.domains.travel_ops.instances.mobility import route_shape as RS
from tests.unit.travel.mobility.test_route_shape_context_v1 import A, B, BUS_LEG, RAIL_LEG, Router, Stations, ShortestLoop, bus_data, context, item, route

KST = ZoneInfo('Asia/Seoul')


def at(hm):
    return datetime.fromisoformat(f'2026-10-18T{hm}:00').replace(tzinfo=KST)


def fixture(rail=False, start='10:01'):
    planned = 'subway_1' if rail else 'bus_405'
    leg = deepcopy(RAIL_LEG if rail else BUS_LEG)
    uses = ['2호선:시청', '2호선:아현'] if rail else ['버스:405']
    ctx = context([leg], planned)
    ctx['options']['not_selected'] = {'option_id': 'not_selected', 'legs': [dict(leg)]}
    got = {'route': route(planned, uses), 'starts_at': at(start), 'ends_at': at('10:21'),
           'eta_min': 20, 'departure_context': ctx}
    places = [{'key': key, 'name': name, 'lat': point[1], 'lon': point[0]}
              for key, name, point in [('a', '서울시청', A), ('b', '아현역', B)]]
    checked = [{'id': str(i), 'source_id': 'public', 'index': i, 'title': p['name'], 'kind': 'activity',
                'day': 1, 'date': '2026-10-18', 'starts_at': start, 'ends_at': end,
                'place': {'name': p['name'], 'latitude': p['lat'], 'longitude': p['lon']}}
               for i, (p, start, end) in enumerate(zip(places, ['09:00', '11:00'], ['10:00', '12:00']))]
    body = {'places': places, 'items': [
        {'seq': i + 1, 'title': c['title'], 'kind': c['kind'], 'place': p['key'],
         'starts_at': at(c['starts_at']).isoformat(), 'ends_at': at(c['ends_at']).isoformat(),
         'detail': {'intake': {'source_id': 'public', 'index': i}}}
        for i, (p, c) in enumerate(zip(places, checked))]}
    return got, places, checked, body


def saved(got, places, checked):
    leg = moves.leg_between(lambda *a: (got, None), *places, at('10:00'), at('11:00'), deep=False)
    return {'items': checked, 'moves': [review._move(*checked, leg, [], 'same-pair')]}, leg


@pytest.mark.parametrize('rail', [False, True])
def test_intake_selected_route_survives_review_and_registration_map_contract(monkeypatch, rail):
    got, places, checked, body = fixture(rail)
    before = deepcopy(got)
    stored, leg = saved(got, places, checked)
    monkeypatch.setattr(RS, '_engine', lambda: (Router(), Stations()))
    monkeypatch.setattr(RS, '_line_order', lambda: ShortestLoop())
    monkeypatch.setattr(RS, '_bus_routes', bus_data)
    shape, = RS.shapes_for_review(stored)
    expected = RAIL_LEG['station_path'] if rail else ['승차', '실제경유', '하차']
    assert shape['rides'][0]['stations'] == expected
    registered = registered_moves.with_review_moves(body, stored)['items'][1]
    detail = registered['detail']
    assert detail['route_def']['planned'] == got['route']['planned']
    assert detail['departure_context']['options'][got['route']['planned']]['legs'] == [RAIL_LEG if rail else BUS_LEG]
    assert list(detail['departure_context']['options']) == [got['route']['planned']]
    registered_shape, = RS.shapes_for_items([item(1, 'activity', A), item(2, 'mobility', detail=detail),
                                             item(3, 'activity', B)])
    assert registered_shape['rides'][0]['stations'] == expected
    assert got == before
    detail['departure_context']['options'][got['route']['planned']]['legs'][0]['from'] = 'changed'
    assert got == before and leg.departure_context == stored['moves'][0]['departure_context']


def test_internal_selected_route_context_does_not_enter_the_public_review_response():
    got, places, checked, _ = fixture()
    stored, _ = saved(got, places, checked)
    before = deepcopy(stored)
    output = review.public(stored)
    assert 'departure_context' in stored['moves'][0]
    assert not {'departure_context', 'selected_option_id', 'uses', 'sig'} & output['moves'][0].keys()
    assert stored == before


def test_unverified_shifted_departure_does_not_reuse_the_old_selected_vehicle():
    got, places, checked, _ = fixture(start='09:00')
    stored, leg = saved(got, places, checked)
    assert not leg.verified and leg.depart == at('10:00')
    assert stored['moves'][0].get('departure_context') is None
    assert stored['moves'][0].get('selected_option_id') is None


@pytest.mark.parametrize('damage', ['version', 'option', 'options_type'])
def test_malformed_engine_context_is_not_registered_as_the_selected_route(damage):
    got, places, checked, body = fixture()
    if damage == 'version': got['departure_context']['schema_version'] = True
    elif damage == 'option': got['departure_context']['options']['bus_405']['option_id'] = 'other'
    else: got['departure_context']['options'] = []
    stored, _ = saved(got, places, checked)
    assert stored['moves'][0].get('departure_context') is None
    move = registered_moves.with_review_moves(body, stored)['items'][1]
    assert move['detail'].get('departure_context') is None
    assert move['detail']['route_def']['planned'] == 'bus'


def test_review_context_without_legacy_uses_still_draws_the_selected_loop(monkeypatch):
    got, places, checked, _ = fixture(rail=True)
    stored, _ = saved(got, places, checked)
    stored['moves'][0]['uses'] = []
    monkeypatch.setattr(RS, '_engine', lambda: (Router(), Stations()))
    monkeypatch.setattr(RS, '_line_order', lambda: ShortestLoop())
    monkeypatch.setattr(RS, '_bus_routes', lambda: None)
    shape, = RS.shapes_for_review(stored)
    assert shape['rides'][0]['stations'] == RAIL_LEG['station_path']

