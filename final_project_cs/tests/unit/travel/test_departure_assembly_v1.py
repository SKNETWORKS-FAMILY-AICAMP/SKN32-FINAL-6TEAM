"""설정·조립·끼움 자리·정확 정류소·안내를 연결한다. 외부 조회는 주입 응답이다."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import composition
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from app.domains.travel_ops.components.watch.departure_revalidation import build_observer
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.ports.data_sources.seoul_bus import select_boardable_arrival
from .mobility.test_departure_observer_v1 import scene as engine_scene, ORIGIN, DESTINATION, NOW
from .test_departure_observer_notice_v1 import scene as notice_scene, NoEvents, t
from .test_bus_boardable_arrival_v1 import snapshot
from .test_bus_boardable_source_v1 import make_source, response_receive_clock  # noqa: F401

POLICY = {'travel.bus_arrival_cache_seconds': 30,
          'mobility.departure_observation.max_provider_age_seconds': 90,
          'mobility.departure_observation.max_provider_clock_ahead_seconds': 2}


class Source:
    def __init__(self):
        self.calls = []
    def boardable_arrival(self, route_id, **kwargs):
        self.calls.append((route_id, kwargs))
        data = snapshot()
        data['stops'][0]['stop_id'] = '1005'
        return select_boardable_arrival(data, route_id=route_id, **kwargs)


def setup(monkeypatch, source=None):
    runtime, context = engine_scene()
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    move, items = notice_scene()
    move.detail['departure_context'] = context
    items[-1].place = dict(latitude=DESTINATION['lat'], longitude=DESTINATION['lon'], name='B')
    previous = Item(item_id=uuid4(), seq=0, kind='activity', title='A', place_id=None,
        starts_at=t('09:00'), ends_at=t('10:00'),
        place=dict(latitude=ORIGIN['lat'], longitude=ORIGIN['lon'], name='A'))
    items.insert(0, previous)
    source = source or Source()
    observer = composition.build_mobility_departure_observer(
        SimpleNamespace(mobility_data_dir='fixture'), SimpleNamespace(bus_arrival=source), guardrails=POLICY)
    return runtime, move, items, source, observer


def test_factory_uses_current_places_policy_exact_stop_and_new_eta(monkeypatch):
    _, move, items, source, observer = setup(monkeypatch)
    original = deepcopy(move)
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == 'ok' and '약 12분' in phrase.render(), phrase.render()
    [(_, kwargs)] = source.calls
    assert kwargs['stop_id'] == '1005' and kwargs['stop_sequence'] == 5
    assert kwargs['ready_at'] == t('10:06') and kwargs['max_age_seconds'] == 30
    assert kwargs['max_provider_age_seconds'] == 90 and kwargs['max_provider_clock_ahead_seconds'] == 2
    assert move == original


def test_actual_source_adapter_cache_and_consumer_are_assembled_together(monkeypatch):
    source, _, http_calls = make_source()
    runtime, move, items, _, observer = setup(monkeypatch, source)
    runtime._v.bus.stops['100'][4]['station_id'] = '101'
    option = move.detail['departure_context']['options']['p']
    for saved_legs in (option['legs'], option['check']['legs']):
        saved_legs[0]['from_stop_id'] = '101'
    for _ in range(2):
        got = observer(move, items, planned={'id': 'p'}, now=NOW, events={})
        assert got['status'] == 'realtime' and got['eta_min'] == 12, got
        assert got['observations'][0]['stop_sequence'] == 5
    assert len(http_calls) == 1


def test_changed_current_place_is_not_replaced_with_saved_coordinates(monkeypatch):
    _, move, items, source, observer = setup(monkeypatch)
    items[0].place['latitude'] += .01
    got = observer(move, items, planned={'id': 'p'}, now=NOW, events={})
    assert got['status'] == 'needs_replan' and got['reason'] == 'place_changed' and source.calls == []


@pytest.mark.parametrize('problem', ['missing_place', 'missing_context', 'missing_visit'])
def test_missing_current_input_is_held_without_using_old_eta(monkeypatch, problem):
    _, move, items, source, observer = setup(monkeypatch)
    if problem == 'missing_place':
        items[0].place = None
    elif problem == 'missing_context':
        move.detail.pop('departure_context')
    else:
        items.pop(0)
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == 'held' and phrase is None and not source.calls


def test_unconfigured_source_revalidates_model_and_keeps_failure_evidence(monkeypatch):
    _, move, items, _, _ = setup(monkeypatch)
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
        SimpleNamespace(bus_arrival=None), guardrails=POLICY)
    got = observer(move, items, planned={'id': 'p'}, now=NOW, events={})
    assert got['status'] == 'model_revalidated' and got['eta_min'] == 16
    assert got['observations'][0]['reason'] == 'bus_arrival_source_unconfigured'


def test_source_exception_is_reported_fatal_without_exposing_exception_text(monkeypatch):
    class Broken:
        def boardable_arrival(self, *a, **kw):
            raise RuntimeError('secret fixture value')
    _, move, items, _, observer = setup(monkeypatch, Broken())
    got = observer(move, items, planned={'id': 'p'}, now=NOW, events={})
    assert got == {'status': 'fatal', 'reason': 'departure_revalidation_failed', 'exception_type': 'RuntimeError'}


def test_team_clear_clears_observer_and_never_returns_success(monkeypatch):
    _, move, items, _, _ = setup(monkeypatch)
    legs.clear()
    got = build_observer(bus_arrival=None)(move, items, planned={'id': 'p'}, now=NOW, events={})
    assert got['status'] == 'fatal' and got['reason'] == 'mobility_observer_unregistered'


def test_disabled_engine_keeps_explicit_legacy_assembly(monkeypatch):
    monkeypatch.setattr(composition, '_configure_mobility', lambda *a: pytest.fail('꺼짐 적재 금지'))
    assert composition.build_mobility_departure_observer(
        SimpleNamespace(mobility_data_dir=''), SimpleNamespace()) is None


@pytest.mark.parametrize('value', [None, 0, -1, True, float('nan'), '90'])
def test_invalid_policy_is_rejected_instead_of_using_numeric_defaults(monkeypatch, value):
    wiring._STATE.update(mode='enabled', kw={})
    policy = dict(POLICY, **{'mobility.departure_observation.max_provider_age_seconds': value})
    with pytest.raises(ValueError):
        composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
            SimpleNamespace(), guardrails=policy)


def test_reminders_only_initializes_engine_but_existing_runtime_is_not_reconfigured(monkeypatch):
    wiring._STATE.update(mode='unconfigured', kw={})
    calls = []
    def configure(settings):
        calls.append(settings)
        wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(composition, '_configure_mobility', configure)
    settings = SimpleNamespace(mobility_data_dir='fixture')
    for _ in range(2):
        assert callable(composition.build_mobility_departure_observer(settings, SimpleNamespace(), guardrails=POLICY))
    assert calls == [settings]


def test_sweeper_entry_passes_assembled_observer_to_actual_reminder_constructor(monkeypatch):
    from scripts import run_sweepers
    from app.domains.travel_ops.ports.data_sources import base
    from app.domains.travel_ops.components.watch import trip_reminders
    settings, sources, observer = SimpleNamespace(), SimpleNamespace(route_events=NoEvents()), object()
    monkeypatch.setattr(run_sweepers, 'get_settings', lambda: settings)
    monkeypatch.setattr(base, 'build_travel_sources', lambda arg: sources)
    monkeypatch.setattr(composition, 'build_mobility_departure_observer', lambda a, b: observer)
    class Reminders:
        def __init__(self, **kwargs):
            assert kwargs['departure_observer'] is observer and kwargs['route_events'] is sources.route_events
        def tick(self):
            return trip_reminders.ReminderTickResult()
    monkeypatch.setattr(trip_reminders, 'TripReminders', Reminders)
    assert run_sweepers._run_trip_reminders('fixture')['fatal'] == 0
    assert run_sweepers._run_trip_reminders('fixture')['stale'] == 0
