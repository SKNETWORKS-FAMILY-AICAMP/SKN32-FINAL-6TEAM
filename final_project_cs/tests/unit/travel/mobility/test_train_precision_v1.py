"""공식 정차 시각 연결과 경계 검증. 실제 도착 측정이 아닌 예정 시간표 검증이다."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import train_precision as TP
from app.domains.travel_ops.instances.mobility.engine.verify_time import Dep, Timetable, Verifier


def doc(stops=None):
    return {'schema_version':1,'source_url':'https://www.data.go.kr/data/15098251/fileData.do',
            'observed_at':'2026-10-12T00:00:00+00:00','runs':[
        {'line':'02호선','day_type':'weekday','dir':'U','train_code':'2180',
         'stops':stops or [['성수',None,36000],['강남',39090,39120],['교대',39210,39270],['성수',43200,None]]}]}


def row(**changes):
    return {'line':'02호선','station_nm':'강남','day_type':'weekday','dir':'U','dep_time':'10:52:00',
            'dest_nm':'성수',**changes}


def test_exact_departure_links_actual_arrival_and_preserves_repeat_station():
    match=TP.TrainPrecision(doc()).match(row())
    assert match.departure_sec==39120
    assert match.arrival_sec(['강남','교대','성수'],'교대')==39210
    assert match.arrival_sec(['강남','교대','성수'],'성수')==43200
    assert match.arrival_sec(['강남','성수'],'성수') is None


@pytest.mark.parametrize('changes',[{'dep_time':'10:52:01'},{'day_type':'holiday'},{'dir':'D'},
                                  {'dest_nm':'신도림'},{'dest_inferred':'chain_v1'}])
def test_same_minute_other_train_day_direction_terminal_and_inferred_do_not_link(changes):
    assert TP.TrainPrecision(doc()).match(row(**changes)) is None


def test_ambiguous_train_code_reuse_does_not_link():
    d=doc();other=copy.deepcopy(d['runs'][0]);other['train_code']='reused';d['runs'].append(other)
    assert TP.TrainPrecision(d).match(row()) is None


@pytest.mark.parametrize('stops',[
    [['강남',39130,39120],['교대',39210,None]],
    [['강남',39090,39120],['교대',39000,None]],
])
def test_reversed_times_are_rejected(stops):
    with pytest.raises(ValueError): TP.TrainPrecision(doc(stops))


def test_missing_arrival_does_not_invent_alighting_time():
    match=TP.TrainPrecision(doc([['강남',39090,39120],['교대',None,39270],['성수',43200,None]])).match(row())
    assert match.arrival_sec(['강남','교대'],'교대') is None


def test_service_day_beyond_midnight_is_kept():
    d=doc([['강남',89970,90000],['교대',90090,None]])
    d['runs'][0]['stops'].append(['성수',90120,None])
    match=TP.TrainPrecision(d).match(row(dep_time='25:00:00'))
    assert match.arrival_sec(['강남','교대'],'교대')==90090


def test_missing_sidecar_falls_back_and_explicit_path_checks_base_hash(tmp_path):
    base=tmp_path/'base.jsonl';base.write_text(json.dumps(row()),encoding='utf-8')
    assert TP.load_for_timetable(base) is None
    d=doc();d['timetable_sha256']=hashlib.sha256(base.read_bytes()).hexdigest()
    p=tmp_path/'other.json.gz'
    with gzip.open(p,'wt',encoding='utf-8') as f:json.dump(d,f)
    assert TP.load_for_timetable(base,p).match(row()) is not None
    assert Timetable.load(base,train_precision_path=p).departures('02호선','강남','weekday')[0].precision is not None
    base.write_text(json.dumps(row(dep_time='10:53:00')),encoding='utf-8')
    with pytest.raises(RuntimeError,match='기준 시간표'): TP.load_for_timetable(base,p)


def test_actual_arrival_rounds_once_and_fallback_remains_conservative():
    v=Verifier.__new__(Verifier);v.lo=SimpleNamespace(travel_min_on_path=lambda *a:2.2)
    match=TP.TrainPrecision(doc()).match(row())
    d=Dep(652,'U','성수',precision=match,departure_sec=39120)
    verdict=SimpleNamespace(path=['강남','교대','성수'])
    ride=v.ride_of('02호선',d,verdict,'강남','교대')
    assert ride==1.5
    assert v._scheduled_arrival_min(d,verdict,'교대',ride)==654
    fallback=Dep(652,'U','성수')
    assert v._scheduled_arrival_min(fallback,verdict,'교대',2.2)==655


@pytest.mark.parametrize('last_min,allowed',[(654,False),(655,True)])
def test_loop_operation_end_uses_absolute_arrival_second(last_min,allowed):
    v=Verifier.__new__(Verifier)
    match=TP.TrainPrecision(doc([['강남',39090,39150],['교대',39270,39300],['성수',43200,None]])).match(row(dep_time='10:52:30'))
    departure=Dep(652,'U','성수',precision=match,departure_sec=39150)
    v.tt=SimpleNamespace(departures=lambda line,station,day:[departure] if station=='강남' else [Dep(last_min,'U','성수')])
    v.lo=SimpleNamespace(terminates_here=lambda *a:False,is_loop=lambda *a:True)
    v.is_origin_station=lambda *a:False
    v.rv=lambda *a:0
    v._disr_edges=lambda *a:set()
    v.dominant_dest=lambda *a:'성수'
    v._passes=lambda *a,**kw:SimpleNamespace(value=True,path=['강남','교대','성수'])
    candidates,dropped,_=v.candidates('02호선','강남','교대','weekday')
    assert bool(candidates)==allowed
    assert dropped.get('운행종료후_한바퀴',0)==int(not allowed)


@pytest.fixture(scope='module')
def real_runtime():
    from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
    root=next(p for p in Path(__file__).resolve().parents if (p/'datasets/mobility/processed').exists())
    rt=build_verifier(data_dir=str(root/'datasets/mobility/processed'),gh_url='',seoul_key='',quiet=True,local_router=False)
    rt._v.lfd_enabled=False
    return rt


@pytest.mark.parametrize('ready,expected',[(39299,655),(39300,655),(39301,662)])
def test_next_train_boundary_uses_exact_ready_second(real_runtime,ready,expected):
    v=real_runtime._v
    result=v.verify_leg(1,{'line':'03호선','from':'교대','to':'양재'},656,'weekday',False,
                        party={},ready_at_sec=ready)
    assert result.depart_min==expected


def test_public_case_catches_valid_transfer_without_changing_walk_speed(real_runtime):
    result=real_runtime.verify_case({'id':'precision-transfer','date':'2026-10-12','depart_at':'10:52',
        'stage':'planning','first_visit':False,'no_alternatives':True,'legs':[
            {'line':'02호선','from':'강남','to':'교대'}, {'line':'03호선','from':'교대','to':'양재'}]})
    rides=[l for l in result.legs if l.depart_min is not None]
    assert [l.depart_min for l in rides]==[652,655]
    assert [l.arrival_sec for l in rides]==[39210,39540]
    assert result.arrive_min==659
    assert real_runtime._v.tw.speed==1.04
