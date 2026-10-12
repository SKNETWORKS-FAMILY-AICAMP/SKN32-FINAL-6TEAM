"""조립→실제 어댑터→지연 재검증→안내 소비를 통제 응답으로 확인한다."""
from datetime import timedelta
from types import SimpleNamespace

from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_arrival_query_clock_v1 import delayed_source
from .test_departure_observer_v1 import NOW
from ..test_departure_assembly_v1 import setup
from ..test_departure_observer_notice_v1 import NoEvents


def assembled(monkeypatch, delay):
    query, requests, clock = delayed_source(monkeypatch, delay=delay)
    def boardable(route_id, **kwargs):
        # fixture의 정책과 조립에서 전달하는 정책이 같음을 확인한 뒤 실제 어댑터로 전달한다.
        assert kwargs.pop('max_age_seconds') == 30
        assert kwargs.pop('max_provider_age_seconds') == 90
        assert kwargs.pop('max_provider_clock_ahead_seconds') == 2
        return query(route_id, **kwargs)
    runtime, move, items, _, observer = setup(monkeypatch, SimpleNamespace(boardable_arrival=boardable))
    return runtime, move, items, observer, requests, clock


def test_assembled_delayed_source_emits_new_departure_and_realtime_eta(monkeypatch):
    _, move, items, observer, requests, _ = assembled(monkeypatch, 2)
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == 'ok', status
    text = phrase.render()
    assert '10:01 출발' in text and '약 13분' in text and '현재 버스 대기 반영' in text
    assert len(requests) == 1


def test_assembled_delay_that_loses_deadline_holds_departure_phrase(monkeypatch):
    _, move, items, observer, requests, _ = assembled(monkeypatch, 120)
    items[-1].starts_at = NOW + timedelta(minutes=8)
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=NOW, departure_observer=observer)
    assert status == 'held' and phrase is None and len(requests) == 1
