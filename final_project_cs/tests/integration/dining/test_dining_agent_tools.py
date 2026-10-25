# -*- coding: utf-8 -*-
"""요식 에이전트 도구(`agent_tools`) — 규칙 판정 · 호출 기록 · 상한 · 실행 내 결과 재사용 · MCP 서버.

합성 가게로만 본다(적재한 자료에 기대지 않는다 — `test_dining_judgment` 와 같은 원칙). DB 가 없으면 통째로 건너뛴다.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager

from app.domains.travel_ops.instances.dining.agent_tools import SPECS, DiningTools, build_mcp, openai_tools

from tests.integration.dining.test_dining_judgment import add_closure, add_hours, at, open_at

MON = at(0, "12:00").date().isoformat()


def _tools(conn, **kw) -> DiningTools:
    @contextmanager
    def connect():
        yield conn
    return DiningTools(connect, **kw)


def _real(conn, uid: str, address: str = "서울특별시 중구 시험로 1") -> None:
    """이름 찾기 · 근처 찾기는 합성 가게를 내보내지 않는다 — 시험 가게를 실제 가게처럼 둔다(지우는 것은 픽스처가 한다)."""
    conn.execute("UPDATE dining.dn_place SET is_synthetic = false, road_address = %s, category = '한식', category_method = 'manual', "
                 "style = '국물요리', style_method = 'manual' "
                 "WHERE place_uid = %s", (address, uid))


def test_open_at_is_the_same_verdict_as_the_ledger_function(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 900, None), (1020, 1320, 1290)])        # 11~15 · 17~22(LO 21:30)
    tools = _tools(conn)
    for start, verdict in (("12:00", "ok"), ("16:00", "bad"), ("21:20", "bad"), ("10:00", "bad")):
        got = tools.call("check_open_at", {"place_uid": uid, "start": at(0, start).isoformat()})
        assert got["verdict"] == verdict, (start, got)
        assert got["open_at_slot"] == open_at(conn, uid, at(0, start))      # 원장 함수 그대로
    assert tools.calls[2]["result"]["reason"].startswith("도착 20분 뒤가 라스트오더")   # 21:20 은 열려 있지만 주문 여유가 없다


def test_unknown_stays_unknown(conn, place):
    uid = place()                                                          # 규칙 없음
    tools = _tools(conn)
    assert tools.call("check_open_at", {"place_uid": uid, "start": at(0, "12:00").isoformat()})["verdict"] == "unknown"
    assert tools.call("check_closed_day", {"place_uid": uid, "date": MON})["verdict"] == "unknown"
    attrs = tools.call("check_attributes", {"place_uid": uid, "wanted": ["halal", "card"]})["attributes"]
    assert attrs["halal"]["state"] == "unknown" and attrs["card"]["state"] == "unknown"
    assert tools.call("live_open_check", {"place_uid": uid, "start": at(0, "12:00").isoformat()})["verdict"] == "unknown"


def test_closed_day_gives_the_rule_text(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])
    add_closure(conn, uid, pattern_kind="weekly", weekday=1)
    got = _tools(conn).call("check_closed_day", {"place_uid": uid, "date": MON})
    assert got["verdict"] == "bad" and got["closed"] is True and got["rules"][0]["weekday"] == 1


def test_find_place_ledger_first_then_map(conn, place):
    uid = place("에이전트국밥", lat=37.5665, lng=126.9780)
    _real(conn, uid)
    name = conn.execute("SELECT name_ko FROM dining.dn_place WHERE place_uid = %s", (uid,)).fetchone()[0]

    class Map:
        asked: list[str] = []

        def search(self, query, size=5, near=None):
            self.asked.append(query)
            return [{"id": "k1", "name": "지도식당", "category": "음식점 > 한식", "category_group": "FD6",
                     "address": "서울 중구 1", "latitude": 37.56, "longitude": 126.97}]

    kakao = Map()
    tools = _tools(conn, kakao=kakao)
    got = tools.call("find_place", {"name": name})
    assert got["source"] == "ledger" and got["place_uid"] == uid and got["match"] == "exact"
    assert kakao.asked == []                                               # 원장에서 찾으면 지도를 부르지 않는다
    other = tools.call("find_place", {"name": "원장에없는이상한가게이름"})
    assert other["source"] == "map" and other["place_uid"] is None and other["needs_review"] is True
    assert kakao.asked == ["원장에없는이상한가게이름"]


def test_calls_are_recorded_limited_and_confirmed_results_are_reused(conn, place):
    uid = place()
    tools = _tools(conn, max_calls=2)
    first = tools.call("check_business", {"place_uid": uid})
    assert first["call_id"] == "c1" and tools.result_of("c1")["verdict"] == "ok"
    assert tools.call("check_business", {"place_uid": uid}) == {**first, "reused": True}
    assert "refused" in tools.call("no_such_tool", {})
    assert "refused" in tools.call("check_open_at", {"place_uid": uid})             # 필수 인자 없음
    tools.call("place_detail", {"place_uid": uid})
    assert "상한" in tools.call("nearby_places", {"lat": 37.5, "lng": 127.0})["refused"]
    assert len(tools.calls) == 2 and len(tools.refused) == 3 and len(tools.reused) == 1


def test_nearby_and_detail(conn, place):
    a = place("근처하나", lat=37.5700, lng=126.9900)
    b = place("근처둘", lat=37.5705, lng=126.9900)                          # 약 55m
    for uid in (a, b):
        _real(conn, uid)
    add_hours(conn, a, 1, [(660, 1320, None)])
    tools = _tools(conn)
    near = tools.call("nearby_places", {"lat": 37.5700, "lng": 126.9900, "radius_m": 100})["places"]
    assert [p["place_uid"] for p in near][:2] == [a, b]
    detail = tools.call("place_detail", {"place_uid": a, "date": MON})
    assert detail["style"] == "국물요리" and detail["intervals"] == [{"open": "11:00", "close": "22:00", "last_order": None}]


def test_the_same_specs_feed_openai_and_mcp(conn, place):
    uid = place()
    assert [t["function"]["name"] for t in openai_tools()] == list(SPECS)
    server = build_mcp(lambda: _tools(conn))
    listed = asyncio.run(server.list_tools())
    assert [t.name for t in listed] == list(SPECS)
    assert all(t.annotations.readOnlyHint for t in listed)
    _, structured = asyncio.run(server.call_tool("check_business", {"place_uid": uid}))
    assert structured["verdict"] == "ok"
