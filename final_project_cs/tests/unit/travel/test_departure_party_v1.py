"""현재 여행 조건의 대조를 조립된 버스/도보 관측에서 확인한다."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from .test_departure_assembly_v1 import setup
from .test_departure_source_gate_v1 import walking
from .test_departure_observer_notice_v1 import NoEvents
from .mobility.test_departure_observer_v1 import NOW


@pytest.mark.parametrize('mode',['bus','walk'])
@pytest.mark.parametrize('condition',['same','size','fatigue','first_visit','unrelated'])
def test_changed_effective_party_holds_before_arrival_lookup_without_mutating_context(monkeypatch,mode,condition):
    if mode == 'bus':
        _,move,items,source,observer = setup(monkeypatch)
    else:
        move,items,source,observer,_ = walking(monkeypatch)
    original = deepcopy(move.detail['departure_context'])
    trip = {'party_size':None,'constraints':{'first_visit':False}}
    if condition == 'size':
        trip['party_size'] = 2
    elif condition == 'fatigue':
        trip['constraints']['mobility_ease'] = 'needs_rest'
    elif condition == 'first_visit':
        trip['constraints']['first_visit'] = True
    elif condition == 'unrelated':
        trip['constraints'].update(budget=50000,payment='card',survey={'party':'자유 문장은 플래그로 추정하지 않음'})
    observed = []
    def checked(*args,**kwargs):
        got = observer(*args,**kwargs)
        observed.append(got)
        return got
    status,phrase = build_departure(move,items,route_events=NoEvents(),routes=None,
        now=NOW,departure_observer=checked,trip=trip)
    [got] = observed
    if condition in ('same','unrelated'):
        assert status == 'ok' and phrase and got['party_check'] == 'matched',got
        assert len(source.calls) == (1 if mode == 'bus' else 0)
    else:
        assert status == 'held' and phrase is None and got['party_check'] == 'changed',got
        assert got['reason'] == ('first_visit_changed' if condition == 'first_visit' else 'party_changed')
        assert source.calls == []
    assert move.detail['departure_context'] == original


@pytest.mark.parametrize('trip',[{'party_size':True},{'constraints':[]},
    {'constraints':{'first_visit':'false'}},{'constraints':{'survey':{'domestic':'true'}}}])
def test_invalid_current_party_is_fatal_without_exposing_trip_values(monkeypatch,trip):
    _,move,items,source,observer = setup(monkeypatch)
    got = observer(move,items,planned={'id':'p'},now=NOW,events={},trip=trip)
    assert got == {'status':'fatal','reason':'departure_revalidation_failed','exception_type':'ValueError'}
    assert source.calls == []


def test_low_level_legacy_call_is_not_labelled_current_party_checked(monkeypatch):
    move,items,_,observer,_ = walking(monkeypatch)
    got = observer(move,items,planned={'id':'walk'},now=NOW,events={})
    assert got['status'] == 'model_revalidated'
    assert got['party_check'] == 'current_trip_not_supplied'
