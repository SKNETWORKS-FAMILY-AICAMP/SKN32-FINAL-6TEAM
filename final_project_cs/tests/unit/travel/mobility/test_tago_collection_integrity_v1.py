"""실제 수집 진입점의 오류/빈 자료·페이지 완전성을 통제 응답으로 검사한다."""
import importlib
import json
from pathlib import Path
import runpy
import sys
import types

import pytest
import requests

SCRIPTS = Path(__file__).resolve().parents[5] / 'datasets/mobility/scripts'


@pytest.fixture
def checked(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return importlib.import_module('_tago_checked')


class Response:
    def __init__(self, payload=None, status=200):
        self.status_code = status
        self.payload = payload
    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def payload(rows=(), total=None, page=1, size=1000, code='00'):
    return {'response': {'header': {'resultCode': code}, 'body': {
        'items': {'item': list(rows)}, 'totalCount': len(rows) if total is None else total,
        'pageNo': page, 'numOfRows': size}}}


def fetch(checked, responses, **kw):
    calls = []
    def get(*args, **kwargs):
        calls.append(kwargs['params'])
        value = responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value
    result = checked.fetch_body('https://example.org', 'SECRET', 'operation', {},
                                get=get, sleep=lambda _: None, **kw)
    return result, calls


@pytest.mark.parametrize('code', ['30', '22', '99', '', None, 0, 'SECRET https://private'])
def test_provider_error_never_becomes_empty_success(checked, code):
    with pytest.raises(checked.CollectionError) as exc:
        fetch(checked, [Response(payload(code=code))])
    assert 'SECRET' not in str(exc.value) and 'https://' not in str(exc.value)


@pytest.mark.parametrize('bad', [None, [], {}, {'response': {}},
                                {'response': {'header': {'resultCode': '00'}}}, ValueError('SECRET')])
def test_malformed_payload_is_not_empty_success(checked, bad):
    with pytest.raises(checked.CollectionError):
        fetch(checked, [Response(bad)])


@pytest.mark.parametrize('field,value', [('totalCount', -1), ('totalCount', True),
    ('totalCount', None), ('pageNo', 0), ('pageNo', 2), ('numOfRows', 0), ('numOfRows', 1001)])
def test_invalid_metadata_rejected(checked, field, value):
    doc = payload()
    doc['response']['body'][field] = value
    with pytest.raises(checked.CollectionError):
        fetch(checked, [Response(doc)])


def test_true_empty_requires_success_and_zero_count(checked):
    doc = payload()
    doc['response']['body']['items'] = ''
    result, calls = fetch(checked, [Response(doc)])
    assert result['items']['item'] == [] and len(calls) == 1


def test_all_pages_and_provider_page_cap_preserved(checked):
    row = {'trainNo': 'A001', 'unknownType': 'verbatim'}
    result, calls = fetch(checked, [Response(payload([row, {'id': 2}], total=3, size=2)),
                                   Response(payload([{'id': 3}], total=3, page=2, size=2))])
    assert result['items']['item'] == [row, {'id': 2}, {'id': 3}]
    assert [c['numOfRows'] for c in calls] == [1000, 2]
    assert [c['pageNo'] for c in calls] == [1, 2]


@pytest.mark.parametrize('second', [payload([{'id': 3}], total=4, page=2, size=2),
    payload([], total=3, page=2, size=2), payload([{'id': 3}], total=3, page=1, size=2),
    payload([{'id': 3}], total=3, page=2, size=1)])
def test_incomplete_or_changed_snapshot_fails(checked, second):
    with pytest.raises(checked.CollectionError):
        fetch(checked, [Response(payload([{'id': 1}, {'id': 2}], total=3, size=2)), Response(second)])


def test_repeated_page_not_counted_twice(checked):
    rows = [{'id': 1}, {'id': 2}]
    with pytest.raises(checked.CollectionError, match='repeated page'):
        fetch(checked, [Response(payload(rows, total=4, size=2)),
                        Response(payload(rows, total=4, size=2, page=2))])


def test_page_budget_stops_before_next_call(checked):
    with pytest.raises(checked.CollectionError, match='page limit'):
        fetch(checked, [Response(payload([{'id': 1}], total=2, size=1))], max_pages=1)


@pytest.mark.parametrize('first', [Response(status=503), Response(status=429),
    Response(payload(code='05')), Response(payload(code='23')), requests.Timeout('SECRET')])
def test_transient_failure_bounded_retry_then_success(checked, first):
    result, calls = fetch(checked, [first, Response(payload())], attempts=2)
    assert result['totalCount'] == 0 and len(calls) == 2


def test_transport_error_does_not_leak_request_url(checked):
    with pytest.raises(checked.CollectionError) as exc:
        fetch(checked, [requests.Timeout('https://example.org/?key=SECRET')], attempts=1)
    assert str(exc.value) == 'transport failure'


def environment(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    monkeypatch.setitem(sys.modules, '_paths', types.SimpleNamespace(
        RAW_MOBILITY=tmp_path, ensure_dirs=lambda: None))
    monkeypatch.setenv('DATA_GO_KR_KEY', 'CONTROLLED')
    monkeypatch.setattr('time.sleep', lambda _: None)
    ids = {'공덕': [{'subwayStationId': 'CONTROLLED_STATION', 'subwayRouteName': '공항철도'}]}
    (tmp_path / 'tago_station_ids.json').write_text(json.dumps(ids), encoding='utf8')
    return ids


def test_actual_collector_failure_does_not_complete_query(checked, monkeypatch, tmp_path):
    environment(monkeypatch, tmp_path)
    monkeypatch.setattr(requests, 'get', lambda *a, **k: Response(payload(code='30')))
    with pytest.raises(checked.CollectionError):
        runpy.run_path(str(SCRIPTS / 'tago_subway_collect.py'))
    assert not (tmp_path / 'tago_timetable_done.json').exists()
    assert (tmp_path / 'tago_timetable.jsonl').read_bytes() == b''


def test_actual_collector_preserves_provider_fields_and_backups(checked, monkeypatch, tmp_path):
    environment(monkeypatch, tmp_path)
    original = b'previous data\n'
    (tmp_path / 'tago_timetable.jsonl').write_bytes(original)
    def get(*args, **kwargs):
        p = kwargs['params']
        row = {'subwayStationId': p['subwayStationId'], 'dailyTypeCode': p['dailyTypeCode'],
               'upDownTypeCode': p['upDownTypeCode'], 'trainNo': 'A001', 'providerFlag': 'unchanged'}
        return Response(payload([row]))
    monkeypatch.setattr(requests, 'get', get)
    runpy.run_path(str(SCRIPTS / 'tago_subway_collect.py'))
    lines = (tmp_path / 'tago_timetable.jsonl').read_text(encoding='utf8').splitlines()[1:]
    assert len(lines) == 6
    assert all(json.loads(line)['raw_item']['trainNo'] == 'A001' for line in lines)
    assert all(json.loads(line)['raw_item']['providerFlag'] == 'unchanged' for line in lines)
    done = json.loads((tmp_path / 'tago_timetable_done.json').read_text(encoding='utf8'))
    assert len(done) == 6
    assert list((tmp_path / '_backup').glob('*/tago_timetable.jsonl'))[0].read_bytes() == original


def test_actual_retry_error_is_not_confirmed_ok_empty(checked, monkeypatch, tmp_path):
    environment(monkeypatch, tmp_path)
    key = 'CONTROLLED_STATION|01|U'
    (tmp_path / 'tago_timetable_done.json').write_text(json.dumps([key]), encoding='utf8')
    (tmp_path / 'tago_timetable.jsonl').touch()
    monkeypatch.setattr(requests, 'get', lambda *a, **k: Response(payload(code='30')))
    runpy.run_path(str(SCRIPTS / 'tago_retry_empty.py'))
    confirmed = json.loads((tmp_path / 'tago_empty_confirmed.json').read_text(encoding='utf8'))
    assert confirmed[key]['status'] == 'error:provider result 30'
    assert (tmp_path / 'tago_timetable.jsonl').read_bytes() == b''


def test_success_checkpoint_survives_next_api_error(checked, monkeypatch, tmp_path):
    environment(monkeypatch, tmp_path)
    calls = []
    def get(*args, **kwargs):
        calls.append(kwargs['params'])
        if len(calls) > 1:
            return Response(payload(code='30'))
        return Response(payload([{'subwayStationId': 'CONTROLLED_STATION',
                                  'dailyTypeCode': '01', 'upDownTypeCode': 'U'}]))
    monkeypatch.setattr(requests, 'get', get)
    with pytest.raises(checked.CollectionError):
        runpy.run_path(str(SCRIPTS / 'tago_subway_collect.py'))
    assert json.loads((tmp_path / 'tago_timetable_done.json').read_text(encoding='utf8')) == [
        'CONTROLLED_STATION|01|U']
    assert len((tmp_path / 'tago_timetable.jsonl').read_text(encoding='utf8').splitlines()) == 1
