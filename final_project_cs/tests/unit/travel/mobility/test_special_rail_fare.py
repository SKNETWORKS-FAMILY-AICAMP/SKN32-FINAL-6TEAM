"""공식 구간별 요금과 조조 기본운임 할인 규칙을 검산한다."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.line_order import LineOrder
from app.domains.travel_ops.instances.mobility.engine.special_rail import surcharge
from app.domains.travel_ops.instances.mobility.engine.verify_time import leg_txt

ENGINE = Path(O.__file__).parent


def verifier():
    rules = json.loads((ENGINE/'rules/rules_v0.3.json').read_text(encoding='utf8'))
    policy = json.loads((ENGINE/'rules/special_rail_fares_v1.json').read_text(encoding='utf8'))
    rules['fare']['subway']['special_lines'] = policy['lines']
    line = policy['lines']['신분당선']
    edges = [{'a':a,'b':b,'distance_m':None,'grade':'확정','travel_min':2}
             for a,b in zip(line['stations'],line['stations'][1:])]
    lo=LineOrder({'built_at':'2026-10-08','lines':{'신분당선':{
        'stations':[{'station_nm':s} for s in line['stations']], 'edges':edges}}})
    return SimpleNamespace(R=rules,lo=lo,sc=None,tw=None)


@pytest.mark.parametrize('a,b,expected', [
    ('신사','강남',700), ('강남','정자',1000), ('정자','광교',1000),
    ('강남','광교',1500), ('신사','정자',1700), ('신사','광교',2200),
    ('강남','강남',0)])
def test_published_zone_combinations_are_direction_independent(a,b,expected):
    v=verifier()
    assert surcharge(v,[{'line':'신분당선','from':a,'to':b}]) == expected
    assert surcharge(v,[{'line':'신분당선','from':b,'to':a}]) == expected


def test_same_zone_in_several_legs_is_not_charged_twice():
    v=verifier()
    assert surcharge(v,[{'line':'신분당선','from':'강남','to':'양재'},
                        {'line':'신분당선','from':'양재','to':'정자'}]) == 1000


def test_unknown_station_or_missing_policy_cannot_become_normal_fare():
    v=verifier()
    assert surcharge(v,[{'line':'신분당선','from':'없는역','to':'강남'}]) is None
    del v.R['fare']['subway']['special_lines']
    assert surcharge(v,[{'line':'신분당선','from':'신사','to':'강남'}]) is None


@pytest.mark.parametrize('board,expected',[(600,2250),(360,1940)])
def test_official_distance_plus_surcharge_and_early_discount(board,expected):
    v=verifier()
    leg={'line':'신분당선','from':'신사','to':'강남'}
    result=SimpleNamespace(label=leg_txt(leg),depart_min=board)
    assert O.subway_fare(v,[leg],[result]) == expected
    assert O.subway_fare_upper(v,[leg],[result]) == expected
    assert not O.fare_is_est(v,[leg],[result])


def test_conflicting_distance_rows_are_excluded():
    policy=verifier().R['fare']['subway']['special_lines']['신분당선']
    conflicts={frozenset((e['a'],e['b'])) for e in policy['excluded_conflicting_edges']}
    confirmed={frozenset((e['a'],e['b'])) for e in policy['confirmed_edges']}
    assert len(conflicts)==2 and len(confirmed)==13
    assert not conflicts & confirmed
