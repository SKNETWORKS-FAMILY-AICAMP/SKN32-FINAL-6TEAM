"""경로 사건 대상과 현재 이동 모델 재검증의 입구를 구분한다."""
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_departure_assembly_v1 import setup
from .test_departure_observer_notice_v1 import scene as bus_notice, t
from .mobility.test_departure_observer_v1 import NOW
from .mobility.test_departure_walk_v1 import scene
from .mobility.test_review_fixes_plan import PLACES


class UnavailableEvents:
    def affecting(self, targets):
        pytest.fail('확인할 대상이 없는 도보는 사건 소스를 조회하지 않아야 합니다')


def walking(monkeypatch, no_path=False):
    _, move, items, source, observer = setup(monkeypatch)
    runtime, context, planned = scene()
    if no_path:
        runtime._v.bike_router = SimpleNamespace(available=lambda: True, route=lambda *a: None,
                                                last_error={'kind': 'no_path'})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    for index, place in ((0, PLACES[0]), (-1, PLACES[1])):
        items[index].place.update(latitude=place['lat'], longitude=place['lon'])
    move.detail['departure_context'] = context
    move.detail['route_def'] = {'planned': 'walk', 'options': [
        {'id': 'walk', 'label': '도보 이동', 'eta_min': 999, 'uses': []}]}
    return move, items, source, observer, planned


@pytest.mark.parametrize('events', [None, UnavailableEvents()])
def test_walk_revalidation_does_not_require_unrelated_event_source(monkeypatch, events):
    move, items, source, observer, planned = walking(monkeypatch)
    status, phrase = build_departure(move, items, route_events=events, routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == 'ok' and f"약 {planned['eta_min']}분" in phrase.render()
    assert '999' not in phrase.render() and '현재 시각 기준 예상' in phrase.render()
    assert '경로 확인' not in phrase.render() and source.calls == []


def test_disconnected_walk_is_held_even_without_incident_source(monkeypatch):
    move, items, _, observer, _ = walking(monkeypatch, no_path=True)
    status, phrase = build_departure(move, items, route_events=None, routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == 'held' and phrase is None


def test_registered_observer_never_sends_old_bus_guidance_without_event_source():
    move, items = bus_notice()
    status, phrase = build_departure(move, items, route_events=None, routes=None, now=t('10:00'),
        departure_observer=lambda *a, **kw: pytest.fail('노선 사건 소스 누락을 먼저 거절해야 합니다'))
    assert status == 'fatal' and phrase is None


def test_registered_observer_holds_missing_route_definition():
    move, items = bus_notice()
    move.detail.pop('route_def')
    status, phrase = build_departure(move, items, route_events=None, routes=None, now=t('10:00'),
        departure_observer=lambda *a, **kw: pytest.fail('검증할 경로 정의가 없습니다'))
    assert status == 'held' and phrase is None


@pytest.mark.parametrize('missing_route', [False, True])
def test_no_observer_keeps_legacy_no_route_contract(missing_route):
    move, items = bus_notice()
    if missing_route:
        move.detail.pop('route_def')
    status, phrase = build_departure(move, items, route_events=None, routes=None, now=t('10:00'))
    assert status == 'no_route' and phrase is not None
