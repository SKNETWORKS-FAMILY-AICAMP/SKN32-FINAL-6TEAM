"""도보 근거 상실 시 조립된 출발 안내가 저장 시각을 대신 보내지 않는다."""
from types import SimpleNamespace
import pytest
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_departure_assembly_v1 import setup
from .test_departure_observer_notice_v1 import NoEvents
from .mobility.test_departure_observer_v1 import NOW
from .mobility.test_departure_walk_v1 import scene
from .mobility.test_review_fixes_plan import PLACES


@pytest.mark.parametrize('failure', ['unavailable', 'unverified_access', 'no_path'])
def test_lost_walk_evidence_never_sends_saved_or_fabricated_guidance(monkeypatch, failure):
    _, move, items, source, observer = setup(monkeypatch)
    runtime, context, _ = scene()
    # 계획 당시에는 정상 보행망을 사용했고, 출발 직전에 근거가 사라진다.
    if failure == 'unavailable':
        runtime._v.bike_router = None
    else:
        runtime._v.bike_router = SimpleNamespace(available=lambda: True,
            route=lambda *args: ({'distance_m': 300, 'optimistic': True}
                                if failure == 'unverified_access' else None),
            last_error={'kind': 'no_path'} if failure == 'no_path' else None)
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kwargs: runtime)
    for index, place in ((0, PLACES[0]), (-1, PLACES[1])):
        items[index].place.update(latitude=place['lat'], longitude=place['lon'])
    move.detail['departure_context'] = context
    route = move.detail['route_def']
    route['planned'] = 'walk'
    route['options'] = [{'id': 'walk', 'label': '도보 이동', 'eta_min': 999, 'uses': []}]
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == ('held' if failure == 'no_path' else 'fatal')
    assert phrase is None
    assert source.calls == []
