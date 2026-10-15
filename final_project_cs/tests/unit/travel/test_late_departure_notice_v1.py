"""미발행 이동의 늦은 재시도 창과 실제 재검증→문구→발행 경로. 외부 조회/실탑승 아님."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.watch import trip_reminders as notices
from .test_departure_source_gate_v1 import walking
from .mobility.test_departure_observer_v1 import NOW


@pytest.fixture
def world(monkeypatch):
    move, items, source, observer, planned = walking(monkeypatch)
    move.starts_at, move.ends_at = NOW, NOW + timedelta(minutes=1)
    items[-1].starts_at = NOW + timedelta(minutes=30)
    trip_id = uuid4()
    state = SimpleNamespace(now=NOW + timedelta(minutes=2), calls=[], payloads={}, items=items)
    trip = {'version': 1, 'locale': 'ko', 'party_size': None, 'constraints': {'first_visit': False}}
    monkeypatch.setattr(notices.PendingStore, 'list', lambda *a, **k: [])
    def enqueue(conn, *, trip_id, key, payload, **kw):
        if payload['kind'] == 'departure':
            assert kw['expected_departure_inputs'] == {'party_size': None, 'constraints': {'first_visit': False}}
        if key in state.payloads:
            return False
        state.payloads[key] = deepcopy(payload)
        return True
    store = SimpleNamespace(tenant_id='late_departure_fixture', active_trip_ids=lambda *a: [trip_id],
        latest=lambda *a: (trip, state.items), message_exists=lambda conn, **kw: kw['key'] in state.payloads,
        enqueue_message=enqueue)
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def transaction(self):
            return nullcontext()
    def observed(*args, **kwargs):
        state.calls.append(kwargs['now'])
        return observer(*args, **kwargs)
    if hasattr(observer, 'validate_basis'):
        observed.validate_basis = observer.validate_basis
    runner = notices.TripReminders(store=store, connection_factory=Connection, clock=lambda: state.now,
        route_events=None, rules=notices.ReminderRules(), departure_observer=observed)
    runner._changed_since = lambda *a: 0
    state.move, state.source, state.planned, state.runner = move, source, planned, runner
    return state


def departures(items, at, *, revalidate=True):
    return [r for r in notices.plan_reminders(items, now=at, rules=notices.ReminderRules(),
        revalidate_departures=revalidate) if r.kind == 'departure']


def test_late_unannounced_feasible_walk_reaches_current_guidance_once(world):
    original = deepcopy(world.items)
    first = world.runner.tick()
    assert len(first.sent) == 1 and not first.fatal and not first.held
    [payload] = world.payloads.values()
    assert '10:02 출발' in payload['text']
    assert '현재 시각 기준 예상' in payload['text'] and '999' not in payload['text']
    assert payload['departure_observation']['status'] == 'model_revalidated'
    assert world.items == original and world.source.calls == []
    again = world.runner.tick()
    assert not again.sent and again.already == 1 and len(world.calls) == 1


@pytest.mark.parametrize('offset, expected', [(-1, 0), (0, 1), (1, 1), (2, 1), (29, 1), (30, 0), (31, 0)])
def test_window_ends_at_next_visit_not_old_movement_end(world, offset, expected):
    got = departures(world.items, NOW + timedelta(minutes=offset))
    assert len(got) == expected
    if got:
        assert got[0].until == world.items[-1].starts_at


def test_late_candidate_that_cannot_arrive_is_held(world):
    world.now = NOW + timedelta(minutes=29)
    result = world.runner.tick()
    assert len(world.calls) == 1 and len(result.held) == 1
    assert not result.sent and not world.payloads and not result.fatal


@pytest.mark.parametrize('status, bucket', [('fatal', 'fatal'), ('needs_replan', 'held')])
def test_failed_late_recheck_is_not_published_and_can_recover(world, status, bucket):
    current = world.runner.departure_observer
    world.runner.departure_observer = lambda *a, **kw: {'status': status, 'reason': 'controlled_failure'}
    failed = world.runner.tick()
    assert len(getattr(failed, bucket)) == 1 and not failed.sent and not world.payloads
    world.runner.departure_observer = current
    recovered = world.runner.tick()
    assert len(recovered.sent) == 1


def test_already_published_late_move_is_skipped_before_observation(world):
    world.payloads[f'departure:{world.move.item_id}'] = {'existing': True}
    result = world.runner.tick()
    assert result.already == 1 and not result.sent and not world.calls


def test_late_window_finds_following_visit_across_midnight_in_sequence_order(world):
    delta = timedelta(hours=13, minutes=58)
    for item in world.items:
        item.starts_at += delta
        if item.ends_at:
            item.ends_at += delta
    world.items[-1].ends_at = world.items[-1].starts_at + timedelta(hours=1)
    world.now = NOW + delta + timedelta(minutes=2)
    world.items.reverse()
    result = world.runner.tick()
    assert len([s for s in result.sent if s['key'].startswith('departure:')]) == 1
    assert not result.fatal and not result.held
    [payload] = [p for p in world.payloads.values() if p['kind'] == 'departure']
    assert '00:00 출발' in payload['text']


def test_without_following_visit_no_extended_candidate(world):
    assert not departures(world.items[:-1], world.now)


def test_legacy_without_observer_keeps_saved_end_window(world):
    assert not departures(world.items, world.now, revalidate=False)
    world.runner.departure_observer = None
    assert not world.runner.tick().sent


def test_next_visit_deadline_also_bounds_overlong_saved_movement(world):
    world.move.ends_at = NOW + timedelta(hours=2)
    assert not departures(world.items, NOW + timedelta(minutes=30))


def test_missing_saved_movement_end_still_uses_next_visit(world):
    world.move.ends_at = None
    assert len(departures(world.items, world.now)) == 1


def test_late_recovery_still_checks_basis_before_enqueue(world):
    world.runner.departure_observer.validate_basis = lambda basis: False
    result = world.runner.tick()
    assert len(result.stale) == 1 and not result.sent and not world.payloads
