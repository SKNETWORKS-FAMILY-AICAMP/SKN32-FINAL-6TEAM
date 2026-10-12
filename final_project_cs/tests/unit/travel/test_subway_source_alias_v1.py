"""출처가 있는 명시적 별명만 적재한다. 역 접미사를 일반적으로 제거하지 않는다."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.instances.mobility.engine.subway_identity import SubwayStationIndex


def payload():
    return {'schema_version': '1.0', 'station_count': 1, 'line_count': 1, 'stations': [
        {'line_id': '1065', 'station_id': '1065006501', 'line': '공항철도',
         'station': '서울', 'query_station': '서울'}],
        'source_aliases': [{'line_id': '1065', 'station_id': '1065006501', 'alias': '서울역',
                            'source_urls': ['https://example.invalid/controlled']} ]}


def test_explicit_source_alias_preserves_official_name_id_and_query():
    doc = payload();original = deepcopy(doc)
    index = SubwayStationIndex(doc, content_sha256='a' * 64)
    assert index.lookup('공항철도', '서울역') == index.lookup('공항철도', '서울')
    assert index.lookup('공항철도', '서울역')['query_station'] == '서울'
    assert index.station_count == 1 and doc == original
    assert index.lookup('5호선', '서울역') is None
    assert index.lookup('공항철도', '서울 역') is None


@pytest.mark.parametrize('changes', [{'line_id': '1005'}, {'station_id': '99999'},
    {'alias': '서울'}, {'alias': ' 서울역'}, {'source_urls': []}, {'source_urls': None}])
def test_bad_or_conflicting_source_alias_fails_load(changes):
    doc = payload();doc['source_aliases'][0].update(changes)
    with pytest.raises(ValueError):SubwayStationIndex(doc, content_sha256='a' * 64)


def test_duplicate_source_alias_fails_load():
    doc = payload();doc['source_aliases'] *= 2
    with pytest.raises(ValueError):SubwayStationIndex(doc, content_sha256='a' * 64)
