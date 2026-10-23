"""동일 시각·정류소의 원 도착값을 선택→재검증→안내까지 잇는다. 실제 승차 측정 아님."""
from app.domains.travel_ops.ports.data_sources.seoul_bus import select_boardable_arrival
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_departure_observer_v1 import NOW, scene, call
from ..test_bus_boardable_arrival_v1 import snapshot
from ..test_departure_observer_notice_v1 import NoEvents, scene as notice_scene


def test_missed_first_bus_selects_second_and_changes_current_notice_eta():
    runtime, context = scene()
    data = snapshot(first=180, second=420)
    data['stops'][0]['stop_id'] = '1005'
    def source(route_id, **kwargs):
        return select_boardable_arrival(data, route_id=route_id, max_age_seconds=30,
            max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2, **kwargs)
    result = call(runtime, context, bus_arrival=source)
    assert result['status'] == 'realtime' and result['observations'][0]['bus_order'] == 2
    assert result['eta_min'] == 12  # 접근6 + 접근후대기1 + 이동3 + 이탈2
    move, items = notice_scene()
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
        now=NOW, departure_observer=lambda *a, **kw: result)
    assert status == 'ok' and '약 12분' in phrase.render() and '약 17분' not in phrase.render()


def test_model_with_unusable_saved_leg_is_fatal_not_a_fabricated_fallback():
    runtime, context = scene()
    for legs in (context['options']['p']['legs'], context['options']['p']['check']['legs']):
        legs[0]['route_id'] = 'missing'
    result = call(runtime, context)
    assert result['status'] == 'fatal' and result['verdict'] == 'unknown'
