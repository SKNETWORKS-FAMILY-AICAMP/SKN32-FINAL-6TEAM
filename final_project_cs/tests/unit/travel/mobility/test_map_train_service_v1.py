"""선택 편성의 일반/급행 근거가 저장 문맥부터 지도 요약까지 남는지 확인한다."""
from datetime import date
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import departure_context as DC
from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility import route_shape as RS


@pytest.mark.parametrize('kinds,expected', [([True], 'express'), ([False], 'local'),
                                           ([True, False], None), ([None], None), ([], None), ([1], None)])
def test_selected_service_is_preserved_only_when_matching_trains_agree(monkeypatch, kinds, expected):
    leg = {'mode':'subway','line':'09호선','from':'노량진','to':'고속터미널'}
    option = {'id':'subway_1','eta_min':8,'_start':664,'_legs':[leg], '_day_type':'weekday',
              '_lr':[SimpleNamespace(label=O.leg_txt(leg), verdict='feasible',depart_min=664,arrive_min=672)]}
    monkeypatch.setattr(O, 'chosen_departures', lambda *args: [(SimpleNamespace(run=SimpleNamespace(express=kind)), SimpleNamespace(path=['노량진','동작','고속터미널'])) for kind in kinds])
    runtime = SimpleNamespace(_v=object(),timetable_built_at='t',rules_version='r')
    context = DC.capture([option],runtime=runtime,origin={},destination={},stage='planning',party={},
                         first_visit=False,service_date=date(2026,10,12),start_min=664)
    assert context['options']['subway_1']['station_services'] == [expected]
    class Stations:
        def get(self,line,name):
            return {'노량진':{'lng':126.94,'lat':37.51},'동작':{'lng':126.98,'lat':37.50},
                    '고속터미널':{'lng':127.00,'lat':37.50}}[name]
    shape=RS.build_shape((126.94,37.51),(127.00,37.50),{'planned':'subway_1','options':[{'id':'subway_1'}]},
                         router=None,sc=Stations(),context=context)
    assert shape['source']=='stations'
    assert shape['rides'][0].get('service')==expected
    assert ('service' in shape['rides'][0]) == (expected is not None)
