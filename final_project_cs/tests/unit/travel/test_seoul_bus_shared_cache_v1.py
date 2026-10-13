"""별도 버스 어댑터가 실제 DB 캐시를 공유하고 순환노선 방향을 보존한다."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.ports.data_sources.cache import DbResponseCache
from app.domains.travel_ops.ports.data_sources.seoul_bus import BASE, KST, SeoulBusArrival


@pytest.fixture
def unique_key():
    # 다른 시험·실제 공개 응답을 지우지 않고 이 시험이 만든 해시 한 줄만 정리한다.
    service_key = 'TEST_ONLY_' + uuid4().hex
    key = ('seoul_bus_arrival', BASE, tuple(sorted({
        'serviceKey': service_key, 'busRouteId': '100100118', 'resultType': 'json'
    }.items())))
    yield service_key, DbResponseCache._hash(key)
    with get_connection() as conn, conn.transaction():
        conn.execute('DELETE FROM source_response_cache WHERE key_hash=%s', (DbResponseCache._hash(key),))


def test_distinct_bus_adapters_share_real_db_without_repeating_the_provider_call(unique_key):
    key, key_hash = unique_key
    observed = datetime.now(KST).replace(microsecond=0) - timedelta(seconds=8)
    calls = []

    def transport(url, params):
        calls.append(1)
        return httpx.Response(200, json={'msgHeader': {'headerCd': '0'}, 'msgBody': {'itemList': [
            {'busRouteId': '100100118', 'stId': '111000181', 'staOrd': str(seq),
             'rtNm': '753', 'stNm': '여행 출발 정류장', 'dir': direction,
             'mkTm': observed.isoformat(sep=' '), 'arrmsg1': message, 'arrmsg2': '출발대기'}
            for seq, direction, message in [(5, '서울역', '4분38초후[2번째 전]'), (90, '종점', '2분후[1번째 전]')]
        ]}})

    first_cache = DbResponseCache(300, get_connection)
    second_cache = DbResponseCache(300, get_connection)
    first = SeoulBusArrival(service_key=key, transport=transport, cache=first_cache)

    def forbidden_call(url, params):
        pytest.fail('둘째 버스 어댑터가 공유 DB 응답 대신 제공처를 다시 호출했습니다')

    second = SeoulBusArrival(service_key=key, transport=forbidden_call, cache=second_cache)
    a = first.arrivals('100100118', stop_id='111000181', stop_sequence=5)
    b = second.arrivals('100100118', stop_id='111000181', stop_sequence=90)
    assert len(calls) == 1 and first_cache.db_stores == 1 and second_cache.db_hits == 1
    assert a['stops'][0]['direction'] == '서울역' and b['stops'][0]['direction'] == '종점'
    assert a['stops'][0]['buses'][0]['eta_seconds'] == 278
    assert b['stops'][0]['buses'][0]['eta_seconds'] == 120
    # PostgreSQL의 세션 시간대 표현은 달라도 최초 확인 시각 자체는 같아야 한다.
    assert datetime.fromisoformat(a['confirmed_at']) == datetime.fromisoformat(b['confirmed_at'])
    assert b['stops'][0]['received_at'] == observed.isoformat(sep=' ')
    assert datetime.fromisoformat(b['confirmed_at']).astimezone(UTC) >= observed.astimezone(UTC)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT source, payload::text, expires_at-fetched_at FROM source_response_cache WHERE key_hash=%s', (key_hash,))
        source, payload, lifetime = cur.fetchone()
    assert source == 'seoul_bus_arrival' and key not in payload
    assert 25 <= lifetime.total_seconds() <= 35  # 공통 300초 대신 버스 30초 유지.
