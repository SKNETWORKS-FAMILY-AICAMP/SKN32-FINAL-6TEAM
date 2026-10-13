"""공식 괄호 병기의 주역명 대응. 통제 시험이며 실제 도착 오차 시험이 아니다."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.instances.mobility.engine.subway_identity import SubwayStationIndex
from app.domains.travel_ops.instances.mobility.engine.subway_departure import boarding_services
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.instances.mobility.engine.line_order import LineOrder
from .test_subway_departure_v1 import scene, call, source


def index(names, line='5호선'):
    rows = [{'line': line, 'station': name, 'query_station': name,
             'line_id': '1005', 'station_id': str(1005000001+i)} for i, name in enumerate(names)]
    return SubwayStationIndex({'schema_version': '1.0', 'station_count': len(rows),
                              'line_count': 1, 'stations': rows}, content_sha256='a'*64)


@pytest.mark.parametrize('main,official', [
    ('신정', '신정(은행정)'), ('오목교', '오목교(목동운동장앞)'),
    ('군자', '군자(능동)'), ('아차산', '아차산(어린이대공원후문)'),
    ('광나루', '광나루(장신대)'), ('천호', '천호(풍납토성)'),
    ('굽은다리', '굽은다리(강동구민회관앞)'), ('올림픽공원', '올림픽공원(한국체대)')])
def test_primary_lookup_preserves_official_id_name_query_and_copy(main, official):
    ix = index([official])
    got = ix.lookup('05호선', main)
    assert got == ix.lookup('5호선', official)
    assert got['station'] == got['query_station'] == official
    assert got['station_id'] == '1005000001'
    got['station_id'] = 'changed'
    assert ix.lookup('5호선', main)['station_id'] == '1005000001'


def test_same_primary_name_is_ambiguous_but_exact_names_still_resolve():
    ix = index(['군자(능동)', '군자(다른곳)'])
    assert ix.lookup('5호선', '군자') is None
    assert ix.lookup('5호선', '군자(능동)')['station_id'] == '1005000001'
    assert ix.lookup('5호선', '군자(다른곳)')['station_id'] == '1005000002'


def test_exact_primary_name_is_never_overridden_by_different_official_id():
    ix = index(['군자', '군자(능동)'])
    assert ix.lookup('5호선', '군자')['station_id'] == '1005000001'
    assert ix.lookup('5호선', '군자(능동)')['station_id'] == '1005000002'


@pytest.mark.parametrize('name,query', [('군자()', '군자'), ('군자(능동)(병기)', '군자'),
    ('군자(능(동))', '군자'), ('(능동)', '능동'), ('군자（능동）', '군자'),
    ('군자 (능동)', '군자'), ('군자(능동)', '군자역'), ('군자(능동)', ' 군자'),
    ('군자(능동)', '능동')])
def test_malformed_or_unrequested_name_transform_is_not_invented(name, query):
    assert index([name]).lookup('5호선', query) is None


@pytest.mark.parametrize('line', ['9호선', '경의중앙선', '공항철도'])
def test_primary_alias_is_limited_to_documented_one_to_eight_lines(line):
    assert index(['군자(능동)'], line).lookup(line, '군자') is None


def world():
    rt, context = scene()
    rt.subway_stations = index(['양평', '영등포구청', '영등포시장(병기)'])
    context['basis'] = input_basis(rt)
    context['options']['p']['subway_identity'] = rt.subway_stations.bind(context['options']['p']['legs'][0])
    return rt, context


def test_parenthetical_terminal_beyond_target_restores_full_service_and_current_departure():
    rt, context = world()
    binding, services = boarding_services(rt, context['options']['p']['legs'][0])
    assert binding['status'] == 'matched'
    assert any(s['terminal'] == '영등포시장' for s in services)
    got = call(rt, context, subway_arrival=source)
    assert got['status'] == 'realtime' and got['leg_results'][0]['depart_min'] == 608


def test_old_unavailable_boarding_binding_requires_replan_before_query():
    rt, context = world()
    context['options']['p']['legs'][0]['from'] = '영등포시장'
    context['options']['p']['check']['legs'][0]['from'] = '영등포시장'
    context['options']['p']['subway_identity'] = {'status': 'unavailable', 'reason': 'station_identity_unmapped'}
    queried = []
    got = call(rt, context, subway_arrival=lambda *a, **kw: queried.append(a))
    assert got['status'] == 'needs_replan' and got['reason'] == 'subway_identity_changed'
    assert queried == []


def test_missing_middle_identity_still_excludes_service_without_synthetic_id():
    rt, context = world()
    # 주역명으로 대응되는 공식 행 자체가 없으면 여전히 장거리 종착 경로를 제외한다.
    doc = deepcopy(rt._v.lo.doc)
    doc['lines']['05호선']['stations'].append({'station_nm': '미수집'})
    doc['lines']['05호선']['edges'].append({'a': '영등포시장', 'b': '미수집', 'grade': '확정',
        'travel_min': 3, 'travel_min_grade': '추정', 'dir_a_to_b': 'U', 'dir_b_to_a': 'D'})
    rt._v.lo = LineOrder(doc)
    _, services = boarding_services(rt, context['options']['p']['legs'][0])
    assert all(s['terminal'] != '미수집' for s in services)
