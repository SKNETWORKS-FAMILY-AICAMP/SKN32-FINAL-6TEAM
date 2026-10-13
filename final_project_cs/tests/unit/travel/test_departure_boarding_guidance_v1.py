"""재계산한 탑승/환승 시각을 실제 문구틀과 원값에 연결한다. 실탑승 아님."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.watch.trip_reminders import build_departure, notice_fields
from .mobility.test_subway_departure_v1 import scene, source, call
from .test_departure_observer_notice_v1 import NoEvents, scene as notice_scene
from .mobility.test_departure_observer_v1 import NOW


def two_legs():
    rt, context = scene()
    leg = {'mode': 'subway', 'line': '05호선', 'from': '영등포구청', 'to': '영등포시장'}
    context['options']['p']['legs'].append(leg)
    context['options']['p']['check']['legs'].append(deepcopy(leg))
    return rt, context


def render(got):
    move, items = notice_scene()
    return build_departure(move, items, route_events=NoEvents(), routes=None, now=NOW,
                           departure_observer=lambda *a, **kw: got)


def test_actual_recalculated_boarding_times_reach_template_values():
    rt, context = two_legs()
    original = deepcopy(context)
    got = call(rt, context, subway_arrival=source)
    steps = got['boarding_steps']
    assert [(s['board_at'][11:16], s['alight_at'][11:16]) for s in steps] == [('10:08', '10:11'), ('10:15', '10:18')]
    assert [s['boarding_basis'] for s in steps] == ['realtime_arrival_prediction', 'timetable_model']
    assert all(s['ride_basis'] == 'model' for s in steps)
    assert steps[0]['train_number'] == '0501' and steps[0]['towards'] == '영등포시장'
    assert 'train_number' not in steps[1]
    status, phrase = render(got)
    payload = notice_fields(phrase)
    assert status == 'ok'
    assert '10:08 양평 승차' in payload['text'] and '10:11 영등포구청 하차' in payload['text']
    assert '10:15 영등포구청 환승' in payload['text'] and '10:18 영등포시장 하차' in payload['text']
    assert '영등포시장 방면' in payload['text'] and '열차 0501' in payload['text']
    assert '현재 도착 예측 반영 · 하차 시각 예상' in payload['text']
    assert '시간표·이동 모델 예상' in payload['text']
    assert payload['values']['boarding_1_board'] == '10:15'
    assert '{boarding_1_board}' in payload['template']
    assert context == original


def test_source_unavailable_uses_model_boarding_without_current_train_claim():
    rt, context = two_legs()
    got = call(rt, context, subway_arrival=lambda *a, **kw: {'status':'unavailable'})
    assert all(s['boarding_basis']=='timetable_model' for s in got['boarding_steps'])
    status, phrase = render(got)
    assert status=='ok' and '10:10 양평 승차' in phrase.render()
    assert '열차 0501' not in phrase.render() and '현재 도착 예측 반영' not in phrase.render()


def test_later_current_train_changes_displayed_transfer_not_saved_time():
    rt, context = two_legs()
    def late(*args, **kw):
        got=source(*args, **kw)
        got['arrival_at']=(NOW+timedelta(minutes=14)).isoformat()
        return got
    got=call(rt, context, subway_arrival=late)
    assert got['boarding_steps'][1]['board_at'][11:16]=='10:20'
    status, phrase=render(got)
    assert status=='ok' and '10:20 영등포구청 환승' in phrase.render()
    assert '10:15 영등포구청 환승' not in phrase.render()


def test_bus_uses_exact_recalculated_stop_names_and_model_alighting():
    from .mobility.test_departure_observer_v1 import scene as bus_scene, call as bus_call, prediction
    rt, context=bus_scene()
    got=bus_call(rt,context,bus_arrival=prediction)
    step=got['boarding_steps'][0]
    leg=context['options']['p']['legs'][0]
    assert (step['mode'],step['service'],step['from'],step['to'])==('bus',leg['route'],leg['from'],leg['to'])
    status,phrase=render(got)
    assert status=='ok' and '10:07' in phrase.render() and str(leg['from'])+' 승차' in phrase.render()


@pytest.mark.parametrize('mutation', ['reverse','before_departure','past_final_arrival','duplicate','naive','missing_station','false_realtime','false_ride_basis','bad_idx','unknown_basis'])
def test_invalid_detailed_guidance_never_emits_partial_or_stale_notice(mutation):
    rt, context=two_legs()
    got=call(rt,context,subway_arrival=source)
    steps=got['boarding_steps']
    if mutation=='reverse': steps[0]['alight_at']=(NOW+timedelta(minutes=1)).isoformat()
    elif mutation=='before_departure': steps[0]['board_at']=(NOW-timedelta(minutes=1)).isoformat()
    elif mutation=='past_final_arrival': steps[-1]['alight_at']=(NOW+timedelta(hours=2)).isoformat()
    elif mutation=='duplicate': steps.append(deepcopy(steps[-1]))
    elif mutation=='naive': steps[0]['board_at']='2026-10-09T10:08:00'
    elif mutation=='missing_station': steps[0]['from']=''
    elif mutation=='false_realtime': steps[1]['boarding_basis']='realtime_arrival_prediction'
    elif mutation=='false_ride_basis': steps[0]['ride_basis']='observed'
    elif mutation=='bad_idx': steps[0]['idx']=True
    else: steps[0]['boarding_basis']='on_time'
    assert render(got)==('fatal',None)


def test_old_callback_without_detail_preserves_compatibility():
    from .test_departure_observer_notice_v1 import result
    status, phrase=render(result())
    assert status=='ok' and '약 22분' in phrase.render()
    assert '구간별 승차 안내' not in phrase.render()


def test_factory_to_notice_preserves_selected_train_and_transfer_time(monkeypatch):
    from app import composition
    from app.domains.travel_ops.instances.mobility import wiring
    from .test_departure_assembly_v1 import setup,POLICY
    rt,context=two_legs()
    _,move,items,_,_=setup(monkeypatch)
    monkeypatch.setattr(wiring.engine_runtime,'get_verifier',lambda **kw:rt)
    move.detail['departure_context']=context
    queries=[]
    class Arrival:
        def boardable_arrival(self,station,**kw):
            queries.append(station)
            for key in ('max_age_seconds','max_provider_age_seconds','max_provider_clock_ahead_seconds'):
                kw.pop(key)
            return source(station,**kw)
    observer=composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='controlled'),SimpleNamespace(bus_arrival=None,subway_arrival=Arrival()),guardrails=dict(POLICY,**{'travel.subway_arrival_cache_seconds':30}))
    status,phrase=build_departure(move,items,route_events=NoEvents(),routes=None,now=NOW,departure_observer=observer)
    assert status=='ok' and '10:15 영등포구청 환승' in phrase.render()
    assert queries==['양평']


def test_midnight_rollover_keeps_next_date_in_template_values():
    from .test_departure_observer_notice_v1 import result
    from datetime import datetime
    start=datetime.fromisoformat('2026-10-09T23:50:00+09:00')
    move,items=notice_scene()
    items[-1].starts_at=datetime.fromisoformat('2026-10-10T01:00:00+09:00')
    got=result(departure_at=start.isoformat(),arrival_at='2026-10-10T00:20:00+09:00',eta_min=30,
               realtime_mode='subway',boarding_steps=[{'idx':0,'mode':'subway','service':'05호선',
               'from':'양평','to':'영등포구청','board_at':'2026-10-09T23:59:00+09:00',
               'alight_at':'2026-10-10T00:10:00+09:00','boarding_basis':'realtime_arrival_prediction','ride_basis':'model'}])
    status,phrase=build_departure(move,items,route_events=NoEvents(),routes=None,now=start,
                                departure_observer=lambda *a,**kw:got)
    assert status=='ok'
    assert phrase.values['boarding_0_board']=='23:59'
    assert phrase.values['boarding_0_alight']=='2026-10-10 00:10'


@pytest.mark.parametrize('seconds',[1,26,59])
def test_first_boarding_keeps_provider_seconds_instead_of_ceil_model_minute(seconds):
    rt,context=scene()
    expected=NOW+timedelta(minutes=8,seconds=seconds)
    def current(*a,**kw):
        return dict(source(*a,**kw),arrival_at=expected.isoformat())
    got=call(rt,context,subway_arrival=current)
    assert got['leg_results'][0]['depart_min']==609
    assert got['boarding_steps'][0]['board_at']==expected.isoformat()
    status,phrase=render(got)
    assert status=='ok' and phrase.values['boarding_0_board']=='10:08'
