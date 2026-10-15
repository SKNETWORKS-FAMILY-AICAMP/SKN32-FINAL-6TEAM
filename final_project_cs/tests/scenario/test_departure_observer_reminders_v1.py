"""로컬 DB 바깥함의 최신 출발값·관측 근거·중복 조회를 검증한다. 외부 전송 없음."""
from datetime import timedelta

from .test_trip_reminders import world, _reminders, _notices, _at, _NoEvents  # noqa: F401


def test_ten_ticks_one_observation_and_latest_eta_in_outbox(world):
    world['clock'].now = _at('10:50')
    calls = []
    def observer(move, items, *, planned, now, events, trip):
        assert trip['party_size'] == 2
        calls.append(move.item_id)
        return {'status': 'realtime', 'departure_at': now.isoformat(),
                'arrival_at': (now + timedelta(minutes=16)).isoformat(), 'eta_min': 16,
                'observations': [{'source': 'fixture/arrival', 'confirmed_at': now.isoformat()}]}
    reminders = _reminders(world, route_events=_NoEvents(), departure_observer=observer)
    assert len(reminders.tick().sent) == 1
    for _ in range(9):
        assert reminders.tick().already == 1
    [(_, payload)] = _notices(world)
    assert len(calls) == 1 and '약 16분' in payload['text']
    assert payload['departure_observation']['observations'][0]['source'] == 'fixture/arrival'


def test_replan_required_is_held_and_keeps_retryable_observation(world):
    world['clock'].now = _at('10:50')
    reminders = _reminders(world, route_events=_NoEvents(), departure_observer=lambda *a, **kw:
        {'status': 'needs_replan', 'reason': 'arrive_late', 'observations': []})
    got = reminders.tick()
    assert not got.sent and not got.fatal and len(got.held) == 1
    assert got.held[0]['departure_observation']['reason'] == 'arrive_late'
    assert _notices(world) == []


def test_failed_revalidation_is_fatal_without_enqueuing_old_guidance(world):
    world['clock'].now = _at('10:50')
    reminders = _reminders(world, route_events=_NoEvents(), departure_observer=lambda *a, **kw:
        {'status': 'fatal', 'reason': 'no_data'})
    got = reminders.tick()
    assert not got.sent and len(got.fatal) == 1 and _notices(world) == []
    assert got.fatal[0]['failed_categories'] == ['departure_observer']
