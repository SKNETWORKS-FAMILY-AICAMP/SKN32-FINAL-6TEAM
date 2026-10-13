"""운영 감시 입구가 안내와 같은 현재 출발 관측을 주입하는지 확인한다."""
from types import SimpleNamespace

from app import composition


def test_default_case_watch_assembles_current_departure_observer(monkeypatch):
    from scripts import run_sweepers
    from app.domains.travel_ops.ports.data_sources import base
    from app.domains.travel_ops.components.watch import trip_watch_cases
    settings = SimpleNamespace()
    sources = SimpleNamespace(route_events=object())
    observer = object()
    monkeypatch.setattr(run_sweepers, 'get_settings', lambda: settings)
    monkeypatch.setattr(run_sweepers, '_run_trip_safety', lambda tenant: {})
    monkeypatch.setattr(base, 'build_travel_sources', lambda settings: sources)
    monkeypatch.setattr(composition, 'build_controller', lambda: SimpleNamespace())
    monkeypatch.setattr(composition, 'build_mobility_departure_observer', lambda a, b: observer)
    class Opener:
        def __init__(self, **kwargs):
            assert kwargs['departure_observer'] is observer
            assert kwargs['route_events'] is sources.route_events
        def tick(self):
            return SimpleNamespace(checked=0, opened=[], existing=[], ran=[], fatal=[], unhandled=[],
                                   pinned=[], unchecked=[])
    monkeypatch.setattr(trip_watch_cases, 'TripWatchCaseOpener', Opener)
    assert run_sweepers._run_trip_watch_cases('fixture')['fatal'] == 0
