"""주입 응답의 식별정보·ETA를 검증한다. 실제 열차 선택/탑승 시험이 아니다."""
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival

FIELDS = {
    'subwayId': 'line_id', 'statnId': 'station_id', 'statnFid': 'previous_station_id',
    'statnTid': 'next_station_id', 'bstatnId': 'terminal_station_id',
    'bstatnNm': 'terminal_station', 'btrainNo': 'train_number', 'ordkey': 'arrival_order',
}


def source(rows):
    def transport(url, params):
        return httpx.Response(200, json={'realtimeArrivalList': rows},
                              request=httpx.Request('GET', url))
    return SeoulSubwayArrival(service_key='controlled-test-key', transport=transport,
                              now=lambda: datetime(2026, 10, 9, 9, 30, tzinfo=ZoneInfo('Asia/Seoul')))


@pytest.mark.parametrize('raw,normalized', FIELDS.items())
def test_matching_fields_survive_normalization(raw, normalized):
    value = '00123' if raw != 'bstatnNm' else '성수'
    row = {'barvlDt': '180', raw: value}
    got = source([row]).arrivals('강남')['trains'][0]
    assert got[normalized] == value
    assert 'raw' not in got


@pytest.mark.parametrize('value', [None, '', ' ', True, False, 1.5, -1, {}, []])
def test_bad_identity_is_not_invented(value):
    row = {key: value for key in FIELDS}
    got = source([row]).arrivals('강남')['trains'][0]
    assert all(got[key] is None for key in FIELDS.values())


def test_missing_identity_and_numeric_id_are_explicit():
    got = source([{'statnId': 1002000222}]).arrivals('강남')['trains'][0]
    assert got['station_id'] == '1002000222'
    assert all(got[key] is None for key in FIELDS.values() if key != 'station_id')


@pytest.mark.parametrize('value,expected', [(0, 0), ('0', 0), (180, 180), ('0180', 180)])
def test_valid_eta_preserves_zero(value, expected):
    got = source([{'barvlDt': value}]).arrivals('강남')['trains'][0]
    assert got['eta_seconds'] == expected and got['eta_status'] == 'valid'


@pytest.mark.parametrize('value', [True, False, -1, '-1', 1.0, 1.5, '', '180.0',
                                  '\u00b2', '\u0661\u0668\u0660', 'NaN', [], {}, '9' * 5000])
def test_invalid_eta_is_visible_without_crashing(value):
    got = source([{'barvlDt': value}]).arrivals('강남')['trains'][0]
    assert got['eta_seconds'] is None and got['eta_status'] == 'invalid'


def test_missing_eta_is_distinct_from_invalid():
    got = source([{}, {'barvlDt': None}]).arrivals('강남')['trains']
    assert all(t['eta_seconds'] is None and t['eta_status'] == 'missing' for t in got)


@pytest.mark.parametrize('rows', [{}, 'not a list', 17, [None], [{'barvlDt': 180}, 'bad row']])
def test_malformed_list_is_not_reported_as_no_trains(rows):
    src = source(rows)
    assert src.arrivals('강남') is None
    assert src.misses['body_error'] == 1  # 보관 전 실패로 세고 잘못된 목록을 재사용하지 않는다.


def test_schema_and_other_line_identity_survive_filter():
    rows = [{'subwayId': '1002', 'statnId': '1002000222', 'barvlDt': '180'},
            {'subwayId': '1007', 'statnId': '1007000000', 'barvlDt': '0'}]
    got = source(rows).arrivals('강남', line='7호선')
    assert got['schema_version'] == '1.1'
    assert len(got['trains']) == 1
    assert got['trains'][0]['station_id'] == '1007000000'
    assert got['trains'][0]['line'] == '7호선'
