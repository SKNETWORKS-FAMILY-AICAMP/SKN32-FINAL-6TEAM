"""안내 미발행 이동의 감시·현재 재탐색을 검증한다. 실제 위치/탑승 측정은 아니다."""
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener, CaseTickResult
from .test_departure_source_gate_v1 import walking
from .mobility.test_departure_observer_v1 import NOW


@pytest.mark.parametrize('offset, published, expected', [(-1, False, 0), (0, False, 1),
    (2, False, 1), (2, True, 0), (30, False, 0)])
def test_only_unannounced_departures_before_next_visit_are_selected(monkeypatch, offset, published, expected):
    move, items, _, _, _ = walking(monkeypatch)
    move.starts_at = NOW
    move.ends_at = NOW + timedelta(minutes=1)
    items[-1].starts_at = NOW + timedelta(minutes=30)
    trip_id = uuid4()
    store = SimpleNamespace(active_trip_ids=lambda conn, now: [trip_id],
        latest=lambda *a: ({}, items), message_exists=lambda *a, **k: published)
    got = TripStore.pending_departures(store, None, now=NOW+timedelta(minutes=offset))
    assert len(got) == expected
    if got:
        assert got == [(trip_id, move)]


@pytest.mark.parametrize('no_path, expected', [(False, 0), (True, 1)])
def test_current_walk_revalidation_reaches_watch_without_event_source(monkeypatch, no_path, expected):
    move, items, _, observer, _ = walking(monkeypatch, no_path=no_path)
    move.starts_at = NOW
    trip_id = uuid4()
    store = SimpleNamespace(latest=lambda *a: ({'constraints': {'first_visit': False}}, items), message_exists=lambda *a, **k: False)
    opener = TripWatchCaseOpener(store=store, check=None, connection_factory=lambda: nullcontext(None),
        clock=lambda: NOW, repository=None, run_case=None, departure_observer=observer)
    result, issues = CaseTickResult(), []
    opener._route(trip_id, move, NOW, result, issues)
    assert len(issues) == expected and not result.fatal
    if issues:
        assert issues[0].detected == 'departure'
        assert issues[0].causes[0]['kind'] == 'no_walk_path'
        prior = issues[0].base_id
        issues[0].causes[0]['checked_at'] = 'different tick'
        assert issues[0].base_id == prior


def test_broken_observation_is_fatal_instead_of_replan_case(monkeypatch):
    move, items, _, _, _ = walking(monkeypatch)
    move.starts_at = NOW
    store = SimpleNamespace(latest=lambda *a: ({}, items), message_exists=lambda *a, **k: False)
    opener = TripWatchCaseOpener(store=store, check=None, connection_factory=lambda: nullcontext(None),
        clock=lambda: NOW, repository=None, run_case=None,
        departure_observer=lambda *a, **k: {'status': 'fatal', 'reason': 'source_failed'})
    result, issues = CaseTickResult(), []
    deferred = []
    monkeypatch.setattr(opener, '_defer_notice', lambda trip, item, report, now, result: deferred.append(report))
    opener._route(uuid4(), move, NOW, result, issues)
    assert len(result.fatal) == 1 and not issues
    assert len(deferred) == 1 and deferred[0]['error_code'] == 'departure_revalidation_failed'
