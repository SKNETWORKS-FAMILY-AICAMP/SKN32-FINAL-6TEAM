"""조립된 이동 관측이 저장된 구간과 현재 방문 장소를 읽고 바깥함에 새 ETA를 넣는다."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

from app import composition
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.mobility import wiring
from .test_trip_reminders import world, _reminders, _notices, _at, _NoEvents  # noqa: F401
from ..unit.travel.mobility.test_departure_observer_v1 import scene
from ..unit.travel.test_departure_assembly_v1 import POLICY


def assemble(world, monkeypatch, *, delay=7):
    runtime, context = scene()
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    calls = []
    class Source:
        def boardable_arrival(self, route_id, *, stop_id, stop_sequence, now, ready_at, **policy):
            calls.append((route_id, stop_id, stop_sequence, policy))
            return {'status': 'predicted', 'source': 'fixture/arrival', 'route_id': route_id,
                    'stop_id': stop_id, 'stop_sequence': stop_sequence,
                    'confirmed_at': now.isoformat(), 'arrival_at': (now+timedelta(minutes=delay)).isoformat()}
    with get_connection() as conn, conn.transaction():
        trip, items = world['store'].latest(conn, world['trip_id'])
        context['party'] = wiring.party_for_trip(trip)
        context['first_visit'] = (trip.get('constraints') or {}).get('first_visit', True)
        move = next(item for item in items if item.seq == 3)
        visits = [item for item in items if item.kind != 'mobility']
        before = [item for item in visits if item.seq < move.seq][-1]
        after = [item for item in visits if item.seq > move.seq][0]
        for key, item in [('from_place', before), ('to_place', after)]:
            context[key] = {'lat': float(item.place['latitude']), 'lon': float(item.place['longitude'])}
        move.detail = {**deepcopy(move.detail), 'departure_context': context, 'route_def': {
            'from': before.title, 'to': after.title, 'planned': 'p',
            'options': [{'id': 'p', 'label': '시험 버스 이동', 'eta_min': 17, 'uses': ['버스:100']}]}}
        world['store'].append_version(conn, trip_id=world['trip_id'], base_version=trip['version'],
            items=items, reason='departure fixture', causes=[])
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
        SimpleNamespace(bus_arrival=Source()), guardrails=POLICY)
    return _reminders(world, route_events=_NoEvents(), departure_observer=observer), calls


def test_assembled_observer_reads_stored_context_and_current_places_once(world, monkeypatch):
    world['clock'].now = _at('10:50')
    reminders, calls = assemble(world, monkeypatch)
    got = reminders.tick()
    assert len(got.sent) == 1 and not got.fatal and not got.held, got
    for _ in range(9):
        assert reminders.tick().already == 1
    [(_, payload)] = _notices(world)
    assert len(calls) == 1 and '약 12분' in payload['text']
    assert payload['departure_observation']['status'] == 'realtime'
    assert payload['departure_observation']['observations'][0]['stop_sequence'] == 5


def test_assembled_delay_is_held_without_enqueuing_stored_seventeen_minutes(world, monkeypatch):
    world['clock'].now = _at('10:50')
    reminders, calls = assemble(world, monkeypatch, delay=24)
    got = reminders.tick()
    assert not got.sent and len(got.held) == 1 and not got.fatal, got
    assert _notices(world) == [] and len(calls) == 1
    assert got.held[0]['departure_observation']['status'] == 'needs_replan'
