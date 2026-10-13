"""현재 장소와 명시적 도보 문맥이 실제 조립된 안내 함수로 전달된다."""
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_departure_assembly_v1 import setup
from .test_departure_observer_notice_v1 import NoEvents
from .mobility.test_departure_observer_v1 import NOW, ORIGIN, DESTINATION
from .mobility.test_departure_walk_v1 import scene, call
from .mobility.test_review_fixes_plan import PLACES


def test_current_walk_eta_reaches_assembled_departure_message(monkeypatch):
    _, move, items, source, observer = setup(monkeypatch)
    runtime, context, planned = scene()
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    for index, place in ((0, PLACES[0]), (-1, PLACES[1])):
        items[index].place.update(latitude=place['lat'], longitude=place['lon'])
    move.detail['departure_context'] = context
    route = move.detail['route_def']
    route['planned'] = 'walk'
    route['options'] = [{'id': 'walk', 'label': '도보 이동', 'eta_min': 999, 'uses': []}]
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == 'ok' and f"약 {planned['eta_min']}분" in phrase.render(), phrase
    assert '999' not in phrase.render() and source.calls == []


def test_changed_walk_coordinates_are_still_held():
    runtime, context, _ = scene()
    got = call(runtime, context, origin=ORIGIN, destination=DESTINATION)
    assert got['status'] == 'needs_replan' and got['reason'] == 'place_changed'
