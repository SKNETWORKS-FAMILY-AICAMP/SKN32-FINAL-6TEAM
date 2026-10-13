"""실제 어댑터의 조회 지연을 통제 시계로 재현한다. 외부 API·실탑승 시험이 아니다."""
from datetime import datetime, timedelta

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources import base
from app.domains.travel_ops.ports.data_sources.seoul_bus import SeoulBusArrival
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_departure_observer_v1 import NOW, ORIGIN, DESTINATION, scene, call, prediction
from ..test_departure_observer_notice_v1 import scene as notice_scene, NoEvents


def delayed_source(monkeypatch, *, delay=2, first=180, second=420, full=False):
    clock = [NOW]
    requests = []
    class ReceiveClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0].astimezone(tz) if tz else clock[0].replace(tzinfo=None)
    monkeypatch.setattr(base, 'datetime', ReceiveClock)
    def transport(url, params):
        requests.append(params.copy())
        clock[0] += timedelta(seconds=delay)
        return httpx.Response(200, json={'msgHeader': {'headerCd': '0'}, 'msgBody': {'itemList': [{
            'busRouteId': '100', 'stId': '1005', 'staOrd': '5', 'mkTm': clock[0].replace(tzinfo=None).isoformat(),
            'arrmsg1': f'{first}초 후', 'arrmsg2': f'{second}초 후',
            'full1': '1' if full else '0', 'full2': '1' if full else '0'}]}})
    source = SeoulBusArrival(service_key='CONTROLLED_PRIVATE_KEY', transport=transport, now=lambda: clock[0])
    def query(route_id, **kwargs):
        return source.boardable_arrival(route_id, max_age_seconds=30,
            max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2, **kwargs)
    return query, requests, clock


def read(query):
    return query('100', stop_id='1005', stop_sequence=5, now=NOW, ready_at=NOW + timedelta(minutes=6))


def test_fresh_response_after_request_start_is_not_future_confirmation(monkeypatch):
    query, requests, clock = delayed_source(monkeypatch)
    got = read(query)
    assert got['status'] == 'predicted', got
    assert datetime.fromisoformat(got['confirmed_at']) == clock[0]
    assert got['evaluated_at'] == clock[0].isoformat()
    assert got['ready_at'] == (NOW + timedelta(minutes=7)).isoformat()
    assert len(requests) == 1


def test_access_starts_after_response_and_skips_vehicle_missed_during_query(monkeypatch):
    query, _, _ = delayed_source(monkeypatch, first=390, second=480)
    got = read(query)
    assert got['status'] == 'predicted' and got['bus_order'] == 2, got
    assert got['excluded'][0]['reason'] == 'arrives_before_ready'


def test_real_source_clock_flows_through_revalidation_and_departure_notice(monkeypatch):
    runtime, context = scene()
    query, requests, clock = delayed_source(monkeypatch)
    got = call(runtime, context, bus_arrival=query)
    assert got['status'] == 'realtime', got
    assert got['checked_at'] == clock[0].isoformat()
    assert got['departure_at'] == (NOW + timedelta(minutes=1)).isoformat()
    assert got['leg_results'][0]['depart_min'] == 608
    move, items = notice_scene()
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None, now=NOW,
        departure_observer=lambda *args, **kwargs: got)
    assert status == 'ok' and '10:01 출발' in phrase.render()
    assert '현재 버스 대기 반영' in phrase.render() and len(requests) == 1


def test_no_boardable_prediction_still_moves_model_departure_after_response(monkeypatch):
    runtime, context = scene()
    query, _, clock = delayed_source(monkeypatch, full=True)
    got = call(runtime, context, bus_arrival=query)
    assert got['status'] == 'model_revalidated', got
    assert got['checked_at'] == clock[0].isoformat()
    assert got['departure_at'] == (NOW + timedelta(minutes=1)).isoformat()
    assert got['leg_results'][0]['depart_min'] >= 612


def test_query_delay_crossing_deadline_does_not_emit_old_guidance(monkeypatch):
    from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
    runtime, context = scene()
    query, requests, _ = delayed_source(monkeypatch, delay=120)
    got = observe(runtime, context, 'p', now=NOW, deadline=NOW + timedelta(minutes=8),
                  origin=ORIGIN, destination=DESTINATION, bus_arrival=query)
    assert len(requests) == 1 and got['status'] == 'needs_replan', got


@pytest.mark.parametrize('evaluation', ['2026-10-09T10:00:02', '2026-10-09T09:59:59+09:00'])
def test_observer_rejects_missing_timezone_or_backwards_evaluation(evaluation):
    runtime, context = scene()
    def bad(*args, **kwargs):
        return dict(prediction(*args, **kwargs), evaluated_at=evaluation)
    assert call(runtime, context, bus_arrival=bad)['status'] == 'fatal'


def test_confirmed_after_evaluation_is_still_rejected():
    runtime, context = scene()
    def bad(*args, **kwargs):
        return dict(prediction(*args, **kwargs), evaluated_at=(NOW + timedelta(seconds=2)).isoformat(),
                    confirmed_at=(NOW + timedelta(seconds=3)).isoformat())
    assert call(runtime, context, bus_arrival=bad)['status'] == 'fatal'
