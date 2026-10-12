"""공식 역ID 연결/내용 교체를 통제 파일로 검증한다. 실제 열차 선택 시험이 아니다."""
from datetime import date
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import runtime as runtime_module
from app.domains.travel_ops.instances.mobility.engine.departure_context import capture, input_basis
from app.domains.travel_ops.instances.mobility.engine.subway_identity import SubwayStationIndex, load
from app.domains.travel_ops.instances.mobility import wiring
from .test_departure_observer_v1 import scene, call


def doc():
    return {'schema_version': '1.0', 'station_count': 3, 'line_count': 2, 'stations': [
        {'line_id': '1005', 'station_id': '1005000522', 'line': '5호선', 'station': '양평', 'query_station': '양평'},
        {'line_id': '1005', 'station_id': '1005000523', 'line': '5호선', 'station': '영등포구청', 'query_station': '영등포구청'},
        {'line_id': '1063', 'station_id': '1063075135', 'line': '경의중앙선', 'station': '양평', 'query_station': '양평'}]}


def write(path, payload=None):
    path.write_text(json.dumps(doc() if payload is None else payload, ensure_ascii=False), encoding='utf8')
    return load(path)


def test_homonyms_use_official_line_ids_and_lookup_returns_a_copy():
    index = SubwayStationIndex(doc(), content_sha256='a' * 64)
    assert index.lookup('05호선', '양평')['station_id'] == '1005000522'
    assert index.lookup('경의중앙선', '양평')['station_id'] == '1063075135'
    copy = index.lookup('5호선', '양평')
    copy['station_id'] = 'wrong'
    assert index.lookup('5호선', '양평')['station_id'] == '1005000522'


@pytest.mark.parametrize('line,station', [('05호선', '양평역'), ('5호선', ' 양평'),
    ('경의선', '양평'), ('005호선', '양평'), (5, '양평'), ('5호선', None)])
def test_no_fuzzy_alias_or_generated_id(line, station):
    assert SubwayStationIndex(doc(), content_sha256='a' * 64).lookup(line, station) is None


@pytest.mark.parametrize('mutation', ['schema', 'rows', 'count_bool', 'count', 'line_count',
    'duplicate_id', 'duplicate_name', 'bad_line_id', 'bad_station_id', 'blank_name',
    'line_id_conflict', 'line_name_conflict'])
def test_invalid_official_index_is_an_explicit_load_failure(mutation):
    payload = doc()
    if mutation == 'schema': payload['schema_version'] = '9'
    elif mutation == 'rows': payload['stations'][0] = None
    elif mutation == 'count_bool': payload['station_count'] = True
    elif mutation == 'count': payload['station_count'] = 2
    elif mutation == 'line_count': payload['line_count'] = 3
    elif mutation == 'duplicate_id': payload['stations'][2]['station_id'] = payload['stations'][0]['station_id']
    elif mutation == 'duplicate_name': payload['stations'][1]['station'] = '양평'
    elif mutation == 'bad_line_id': payload['stations'][0]['line_id'] = True
    elif mutation == 'bad_station_id': payload['stations'][0]['station_id'] = '000'
    elif mutation == 'blank_name': payload['stations'][0]['query_station'] = ' '
    elif mutation == 'line_id_conflict': payload['stations'][2]['line_id'] = '1005'
    elif mutation == 'line_name_conflict': payload['stations'][2]['line'] = '5호선'
    with pytest.raises(ValueError): SubwayStationIndex(payload, content_sha256='a' * 64)


def test_default_path_registers_the_authoritative_file():
    assert runtime_module.default_paths()['subway_stations'].name == 'subway_realtime_stations_20260902_v1.json'


def capture_scene(tmp_path):
    path = tmp_path / 'stations.json'
    index, signature = write(path)
    rt, _ = scene()
    rt.subway_stations, rt.subway_station_source = index, signature
    leg = {'mode': 'subway', 'line': '05호선', 'from': '양평', 'to': '영등포구청'}
    option = {'id': 'rail', 'eta_min': 10, '_start': 600, '_legs': [leg], '_check': {'legs': [leg]}}
    context = capture([option], runtime=rt, origin={'lat': 37.5, 'lon': 127.0},
        destination={'lat': 37.6, 'lon': 127.0}, stage='planning', party={}, first_visit=False,
        service_date=date(2026, 10, 9), start_min=600)
    return path, rt, option, context


def test_capture_carries_exact_ids_and_content_version_without_mutating_legs(tmp_path):
    _, rt, option, context = capture_scene(tmp_path)
    assert context['basis']['subway_station_version'] == rt.subway_stations.content_sha256
    binding = context['options']['rail']['subway_identity']
    assert binding['station_id'] == '1005000522' and binding['target_station_id'] == '1005000523'
    assert binding['line_id'] == '1005' and binding['query_station'] == '양평'
    assert 'station_id' not in option['_legs'][0]
    binding['station_id'] = 'bad'
    assert rt.subway_stations.lookup('5호선', '양평')['station_id'] == '1005000522'


def test_absent_index_is_explicit_in_captured_rail_option(tmp_path):
    _, rt, option, _ = capture_scene(tmp_path)
    rt.subway_stations = None
    rt.subway_station_source = (str(tmp_path / 'absent.json'), None)
    context = capture([option], runtime=rt, origin={}, destination={}, stage='planning',
                      party={}, first_visit=False, service_date=date(2026, 10, 9), start_min=600)
    assert context['basis']['subway_station_version'] is None
    assert context['options']['rail']['subway_identity']['status'] == 'unavailable'


def test_runtime_detects_content_change_even_if_mtime_is_identical(tmp_path):
    path, rt, _, _ = capture_scene(tmp_path)
    old = path.stat()
    payload = doc()
    payload['stations'][1]['station_id'] = '1005000524'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf8')
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    assert 'subway_stations' in rt.changed_sources()
    # 저장했던 런타임의 내용 판은 파일 새 값으로 바뀌지 않는다.
    assert input_basis(rt)['subway_station_version'] != hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_detects_deletion_and_later_creation(tmp_path):
    path, rt, _, _ = capture_scene(tmp_path)
    path.unlink()
    assert 'subway_stations' in rt.changed_sources()
    rt.subway_stations, rt.subway_station_source = load(path)
    assert not rt.changed_sources()
    write(path)
    assert 'subway_stations' in rt.changed_sources()


def test_save_gate_checks_station_content_without_loading_timetable(tmp_path, monkeypatch):
    path, rt, _, context = capture_scene(tmp_path)
    monkeypatch.setitem(wiring._STATE, 'mode', 'enabled')
    monkeypatch.setattr(runtime_module, 'default_paths', lambda: {'subway_stations': path})
    assert wiring.validate_departure_basis(context['basis'])
    payload = doc()
    payload['stations'][1]['station_id'] = '1005000524'
    write(path, payload)
    assert not wiring.validate_departure_basis(context['basis'])
    assert input_basis(rt) == context['basis']


@pytest.mark.parametrize('version', [True, 17, 'a', 'G' * 64])
def test_save_gate_rejects_invalid_station_version(version, monkeypatch):
    monkeypatch.setitem(wiring._STATE, 'mode', 'enabled')
    with pytest.raises(ValueError):
        wiring.validate_departure_basis({'timetable_built_at': 'a', 'rules_version': 'r',
                                         'subway_station_version': version})


def test_tampered_saved_identity_is_rejected_before_model_or_source(tmp_path):
    _, rt, _, context = capture_scene(tmp_path)
    from .test_departure_observer_v1 import ORIGIN, DESTINATION
    context['from_place'], context['to_place'] = ORIGIN, DESTINATION
    context['options']['p'] = context['options'].pop('rail')
    option = context['options']['p']
    option['option_id'] = 'p'
    option['check'].update(walk_place_in=1, walk_stop_in=1, walk_stop_out=1, walk_place_out=1)
    option['subway_identity']['station_id'] = 'other'
    rt.verify_case = lambda *a, **kw: pytest.fail('다른 역의 문맥으로 계산하면 안 됨')
    got = call(rt, context, bus_arrival=lambda *a, **kw: pytest.fail('조회하면 안 됨'))
    assert got['status'] == 'needs_replan' and got['reason'] == 'subway_identity_changed'


def test_manual_runtime_keeps_legacy_basis():
    rt = SimpleNamespace(timetable_built_at='a', rules_version='r')
    assert input_basis(rt) == {'timetable_built_at': 'a', 'rules_version': 'r'}
