"""공식 호선ID를 주입한 필터 회귀. 실제 열차 도착 오차를 측정하지 않는다."""
import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival


@pytest.mark.parametrize('line_id,line', [('1081', '경강선'), ('1093', '서해선'), ('1094', '신림선')])
def test_official_line_id_is_not_lost_by_named_filter(line_id, line):
    def transport(url, params):
        return httpx.Response(200, json={'realtimeArrivalList': [{'subwayId': line_id, 'barvlDt': '180'}]},
                              request=httpx.Request('GET', url))
    got = SeoulSubwayArrival(service_key='controlled-test-key', transport=transport).arrivals('테스트역', line=line)
    assert len(got['trains']) == 1
    assert got['trains'][0]['line'] == line and got['trains'][0]['line_id'] == line_id


def test_unknown_line_id_remains_explicit():
    def transport(url, params):
        return httpx.Response(200, json={'realtimeArrivalList': [{'subwayId': 'unknown-id', 'barvlDt': '180'}]},
                              request=httpx.Request('GET', url))
    got = SeoulSubwayArrival(service_key='controlled-test-key', transport=transport).arrivals('테스트역')
    assert got['trains'][0]['line'] == 'unknown-id'
