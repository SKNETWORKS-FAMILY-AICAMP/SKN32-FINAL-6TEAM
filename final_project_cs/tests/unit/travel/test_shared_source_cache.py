# -*- coding: utf-8 -*-
"""바깥 소스 호출을 **항목 수가 아니라 소스 단위**로 — 서울 한 번 조회(ITS) + 프로세스를 건너 나누는 응답 캐시. `[2026-10-03 사용자]`

☆측정(`wiki/records/reports/2026-10-03_감시_외부호출_측정_리포트.md`): 한 틱의 요청은 **서로 다른 장소 수**에 비례했다(교통 돌발 ITS · 날씨가 장소마다 한 번). 이 PC 운영 로그에서 ITS 하루 한도(1,000)가
9/30 · 10/2 에 찼고(응답 4001) 그 날 점검 항목 946 · 830개가 「모름(치명)」이 됐다. 게다가 응답 캐시가 **프로세스 안 메모리**라 일꾼(회차마다 새 프로세스)에서는 틱 사이에 비었다.

★지키려는 것
 ①서울 안 장소가 몇 개든 ITS 요청은 **1건**이고 거리로 거르는 결과는 전과 같다. 서울 밖 장소는 전처럼 그 장소의 상자로 묻는다
 ②공유 캐시: 한 프로세스가 받은 공개 소스 응답을 **다른 프로세스**(새 캐시 객체)가 유지 시간 안에서 다시 안 부른다 — 처음 받아 온 시각을 그대로 준다
 ③허용 소스만 DB 에 둔다(고객 검색어가 담기는 소스는 메모리만) · 요청 인자의 서비스 키가 DB 에 **남지 않는다**(열쇠는 해시)
 ④DB 가 안 되면 메모리 캐시로 계속한다(소스 호출을 막지 않는다) — 실패는 세고, 잠시 DB 를 건너뛴다

재현:

    python -m pytest tests/unit/travel/test_shared_source_cache.py -v
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.travel import its_traffic
from app.infrastructure.travel.cache import DbResponseCache, ResponseCache
from app.infrastructure.travel.its_traffic import KST, ItsTrafficEvents

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=KST)


def _resp(payload):
    return httpx.Response(200, json=payload, request=httpx.Request("GET", "https://x"))


def _ok(items):
    return {"header": {"resultCode": 0, "resultMsg": "SUCCESS"}, "body": {"totalCount": len(items), "items": items}}


def _event(lat, lon, message="<공사>::삼일대로::a::b::진행방향 전체차로::[공사/통제] 전면"):
    return {"type": "시군도", "eventType": "공사", "eventDetailType": "", "startDate": "20260901000000", "endDate": "20261031000000",
            "coordX": str(lon), "coordY": str(lat), "roadName": "삼일대로", "roadNo": "0", "lanesBlockType": "", "lanesBlocked": "",
            "message": message, "linkId": "1", "roadDrcType": ""}


class _Counting:
    """ITS 가짜 전송 — 부른 횟수와 인자를 센다."""

    def __init__(self, items):
        self.items, self.calls = items, []

    def __call__(self, url, params):
        self.calls.append(dict(params))
        return _resp(_ok(self.items))


def _its(transport, cache=None):
    return ItsTrafficEvents(service_key="secret-key-123", now=lambda: NOW, transport=transport, cache=cache)


# ── ① 서울 한 번 조회 ─────────────────────────────────────────────

def test_twenty_places_in_seoul_make_one_request_and_each_place_still_sees_only_its_own_events():
    near_a = _event(37.5612, 126.9922)                         # 남산 — 첫 장소 바로 옆
    near_z = _event(37.4980, 127.0270)                         # 강남 — 마지막 장소 바로 옆
    transport = _Counting([near_a, near_z])
    its = _its(transport, ResponseCache(ttl_seconds=300))
    places = [(37.5610, 126.9920)] + [(37.52 + 0.001 * i, 127.00 + 0.001 * i) for i in range(18)] + [(37.4981, 127.0271)]
    results = [its.near(latitude=lat, longitude=lon, at=NOW) for lat, lon in places]

    assert len(transport.calls) == 1                           # ★전에는 20건(장소마다 상자)
    assert transport.calls[0]["minX"] == its_traffic.SEOUL_BOX[0] and transport.calls[0]["maxY"] == its_traffic.SEOUL_BOX[3]
    assert all(r["box"] == "seoul" and r["total_in_box"] == 2 for r in results)
    assert len(results[0]["for_place"]) == 1 and results[0]["for_place"][0]["distance_m"] < 100      # 남산 장소는 남산 사건만
    assert len(results[-1]["for_place"]) == 1 and results[-1]["for_place"][0]["distance_m"] < 100    # 강남 장소는 강남 사건만
    assert all(len(r["for_place"]) == 0 for r in results[1:-1])                                      # 사이 장소들은 둘 다 반경 밖


def test_a_place_outside_seoul_asks_with_its_own_box_as_before():
    transport = _Counting([])
    its = _its(transport, ResponseCache(ttl_seconds=300))
    busan = its.near(latitude=35.1796, longitude=129.0756, at=NOW)
    seoul = its.near(latitude=37.5610, longitude=126.9920, at=NOW)
    assert busan["box"] == "place" and seoul["box"] == "seoul" and len(transport.calls) == 2
    assert transport.calls[0]["minX"] < 129.07 < transport.calls[0]["maxX"] and transport.calls[0]["maxX"] - transport.calls[0]["minX"] < 0.1


# ── ② 프로세스를 건너 나누는 캐시 ─────────────────────────────────

SOURCE = "its"                                        # 허용 소스 — 시험 줄은 이 이름 + 고유 열쇠로 구분해 지운다


@pytest.fixture()
def clean_table():
    def wipe():
        with get_connection() as conn, conn.transaction():
            conn.execute("DELETE FROM source_response_cache WHERE source IN ('its', 'probe', 'kakao_local')")
    wipe()
    yield
    wipe()


def _cache(**kwargs):
    return DbResponseCache(300, get_connection, **kwargs)


def _key(name=SOURCE, key="secret-key-123"):
    return (name, "https://example.test/feed", (("apiKey", key), ("x", "1")))


def test_a_second_process_reuses_what_the_first_one_fetched_with_the_original_time(clean_table):
    first, second = _cache(), _cache()                        # 서로 다른 객체 = 서로 다른 프로세스
    fetched = datetime(2026, 10, 3, 3, 0, tzinfo=UTC)
    first.put(_key(), {"events": [1, 2, 3]}, fetched_at=fetched)

    got = second.get(_key())
    assert got is not None and got[0] == {"events": [1, 2, 3]} and got[1] == fetched                 # ★처음 받아 온 시각 그대로
    assert second.db_hits == 1 and second.hits == 1
    assert second.get(_key()) is not None and second.db_hits == 1                                     # 둘째부터는 메모리


def test_an_expired_row_is_not_served(clean_table):
    first = _cache()
    first.put(_key(), {"a": 1})
    with get_connection() as conn, conn.transaction():
        conn.execute("UPDATE source_response_cache SET expires_at = now() - interval '1 second' WHERE source=%s", (SOURCE,))
    assert _cache().get(_key()) is None


def test_the_xml_string_of_a_feed_round_trips(clean_table):
    _cache().put(_key("its"), "<root><a>1</a></root>")
    assert _cache().get(_key("its"))[0] == "<root><a>1</a></root>"


def test_only_allowed_sources_reach_the_db_and_the_service_key_is_not_stored(clean_table):
    cache = _cache(shared_sources=frozenset({"probe"}))
    cache.put(_key("probe", key="TOP-SECRET-API-KEY"), {"ok": True})
    cache.put(_key("kakao_local", key="TOP-SECRET-API-KEY"), {"user_query": "내 집 주소"})            # 고객 입력이 담길 수 있는 소스 — 메모리만
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT key_hash, source, payload::text FROM source_response_cache WHERE source IN ('probe', 'kakao_local')")
        rows = cur.fetchall()
    assert [r[1] for r in rows] == ["probe"]
    assert "TOP-SECRET-API-KEY" not in " ".join(" ".join(str(c) for c in row) for row in rows)       # 열쇠는 해시 — 키 원문이 DB 에 없다
    assert cache.get(_key("kakao_local", key="TOP-SECRET-API-KEY")) is not None                       # 메모리에서는 그대로 쓴다


def test_a_broken_db_degrades_to_memory_and_is_skipped_for_a_while():
    calls = []

    def broken():
        calls.append(1)
        raise ConnectionError("db down")

    cache = DbResponseCache(300, broken)
    cache.put(_key(), {"v": 1})                                  # 던지지 않는다
    assert cache.get(_key())[0] == {"v": 1}                      # 메모리에서 나온다
    assert cache.db_errors == 1 and len(calls) == 1
    cache.put(_key(key="other"), {"v": 2})                       # 쉬는 동안은 DB 를 다시 건드리지 않는다
    assert cache.get(_key(key="third")) is None and len(calls) == 1


def test_a_source_adapter_through_the_shared_cache_hits_the_network_once_across_processes(clean_table):
    transport_one, transport_two = _Counting([_event(37.5612, 126.9922)]), _Counting([_event(37.5612, 126.9922)])
    first = _its(transport_one, _cache()).near(latitude=37.5610, longitude=126.9920, at=NOW)
    second = _its(transport_two, _cache()).near(latitude=37.5700, longitude=126.9800, at=NOW + timedelta(minutes=10))   # 다른 프로세스 · 다른 장소
    assert len(transport_one.calls) == 1 and transport_two.calls == []                                # ★둘째 프로세스는 바깥에 안 나갔다
    assert first["total_in_box"] == second["total_in_box"] == 1
