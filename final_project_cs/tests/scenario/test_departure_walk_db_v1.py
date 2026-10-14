"""새 도보 문맥의 DB 왕복과 현재 안내·중복 방지를 실제 저장소로 확인한다."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app import composition
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.mobility import wiring
from .test_trip_reminders import world, _reminders, _notices, _at, _NoEvents  # noqa: F401
from ..unit.travel.mobility.test_departure_walk_v1 import scene
from ..unit.travel.test_departure_assembly_v1 import POLICY


@pytest.mark.parametrize('no_path', [False, True])
def test_stored_walk_is_revalidated_once_or_held_on_disconnection(world, monkeypatch, no_path):
    runtime, context, _ = scene()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True,
        route=lambda *a: None if no_path else {'distance_m': 300},
        last_error={'kind': 'no_path'} if no_path else None)
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    with get_connection() as conn, conn.transaction():
        trip, items = world['store'].latest(conn, world['trip_id'])
        context['party'] = wiring.party_for_trip(trip)
        context['first_visit'] = (trip.get('constraints') or {}).get('first_visit', True)
        move = next(item for item in items if item.seq == 10)
        before = next(item for item in items if item.seq == 9)
        after = next(item for item in items if item.seq == 11)
        after.starts_at += timedelta(minutes=10)
        for key, item in [('from_place', before), ('to_place', after)]:
            context[key] = {'lat': float(item.place['latitude']), 'lon': float(item.place['longitude'])}
        move.detail = {**deepcopy(move.detail), 'departure_context': context, 'route_def': {
            'from': before.title, 'to': after.title, 'planned': 'walk',
            'options': [{'id': 'walk', 'label': '도보 이동', 'eta_min': 999, 'uses': []}]}}
        world['store'].append_version(conn, trip_id=world['trip_id'], base_version=trip['version'],
            items=items, reason='departure walk fixture', causes=[])
    world['clock'].now = _at('19:20')
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
        SimpleNamespace(bus_arrival=None), guardrails=POLICY)
    reminders = _reminders(world, route_events=_NoEvents(), departure_observer=observer)
    got = reminders.tick()
    if no_path:
        assert len(got.held) == 1 and not got.sent and not got.fatal, got
        assert not _notices(world)
        assert got.held[0]['departure_observation']['reason'] == 'no_walk_path'
    else:
        assert len(got.sent) == 1 and not got.held and not got.fatal, got
        for _ in range(9):
            assert reminders.tick().already == 1
        [(_, payload)] = _notices(world)
        assert '999' not in payload['text'] and '약 5분' in payload['text']
        assert payload['departure_observation']['status'] == 'model_revalidated'
        assert payload['departure_observation']['observations'][0]['source'] == 'walking_network'
