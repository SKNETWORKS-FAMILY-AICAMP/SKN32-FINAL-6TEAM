# -*- coding: utf-8 -*-
"""일정 항목의 장소 정보 — **요식 원장이 먼저**. `[2026-09-29 사용자 지적 · ui 세션 전달]`

★전에는 선택 일정 상세에 이름·시각·좌표만 있었고, 채팅의 「주소 알려 줘」는 관광공사에서 이름으로 다시 찾기만 해서 원장에
  주소가 있는 식당도 「모름」이었다. 이 시험은 원장에 **합성 식당**(`is_synthetic`)을 넣고 끝나면 지운다 — 개발 DB 의 실제 식당에
  기대지 않는다(다른 세션이 바꿀 수 있다).
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.places.place_info import ledger_info, place_info


@pytest.fixture()
def ledger_place():
    uid = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO dining.dn_place (place_uid, name_ko, area, record_status, is_synthetic, road_address, "
                    "phone, category, category_method) VALUES (%s,'시험 한식당','서울','active',true,"
                    "'서울특별시 종로구 시험로 1','02-000-0000','한식','manual')", (uid,))
        for code, detail in (("michelin", "셀렉티드 (2026)"), ("card_payment", None), ("parking", None)):
            cur.execute("INSERT INTO dining.dn_attribute (place_uid, source_code, attr_code, value_state, value_detail, "
                        "extract_method, valid_from, entered_by, verified_at) "
                        "VALUES (%s,'michelin_guide',%s,'yes',%s,'manual',%s,'test',now())",
                        (uid, code, detail, date(2026, 9, 29)))
        cur.execute("INSERT INTO dining.dn_hours_rule (place_uid, source_code, rule_kind, weekday, coverage, break_state, "
                    "extract_method, rules_version, valid_from, entered_by, verified_at) VALUES "
                    "(%s,'tourapi_kor_food','weekly',1,'intervals','none','manual','test',%s,'test',now()) RETURNING rule_id",
                    (uid, date(2026, 9, 29)))
        rule = cur.fetchone()[0]
        cur.execute("INSERT INTO dining.dn_hours_interval (rule_id, seq, open_min, close_min, last_order_min, "
                    "last_order_state) VALUES (%s,1,660,1320,1260,'present')", (rule,))
    yield str(uid)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM dining.dn_hours_interval WHERE rule_id IN "
                    "(SELECT rule_id FROM dining.dn_hours_rule WHERE place_uid=%s)", (uid,))
        for table in ("dn_hours_rule", "dn_attribute", "dn_place"):
            cur.execute(f"DELETE FROM dining.{table} WHERE place_uid=%s", (uid,))


def test_the_ledger_gives_address_phone_category_hours_tags_and_michelin(ledger_place):
    with get_connection() as conn:
        info = ledger_info(conn, ledger_place)
    assert (info["address"], info["phone"], info["category"]) == ("서울특별시 종로구 시험로 1", "02-000-0000", "한식")
    assert info["hours"] == [{"day": "월", "weekday": 1, "open": "11:00", "close": "22:00", "last_order": "21:00"}]
    assert info["tags"] == ["card_payment", "michelin", "parking"]
    assert info["michelin"] == {"level": "셀렉티드", "year": 2026}
    assert info["source"] == "dining_ledger" and "ⓒ한국관광공사" in info["source_note"]   # 영업시간 출처 표시


def test_a_trip_place_linked_to_the_ledger_shows_the_ledger(ledger_place):
    place = {"place_id": uuid4(), "name": "시험 한식당", "attributes": {"dining_place_uid": ledger_place}}
    with get_connection() as conn:
        info = place_info(conn, "any_tenant", place)
    assert info["source"] == "dining_ledger" and info["address"] == "서울특별시 종로구 시험로 1"


def test_a_place_outside_the_ledger_falls_back_to_its_own_attributes():
    place = {"place_id": uuid4(), "name": "경복궁", "attributes": {"source": "tour_api", "address": "서울 종로구 사직로 161"}}
    with get_connection() as conn:
        info = place_info(conn, "any_tenant_" + uuid4().hex[:6], place)
    assert info["source"] == "tour_api" and info["address"] == "서울 종로구 사직로 161"
    assert info["source_note"] == "ⓒ한국관광공사" and info["hours"] is None and info["tags"] == []


def test_the_chat_answers_the_address_from_the_ledger_first(ledger_place):
    from app.domains.travel_ops.components.conversation.trip_facts import look_up_place

    found = look_up_place({"place_id": uuid4(), "name": "시험 한식당", "kind": "dining",
                           "attributes": {"dining_place_uid": ledger_place}}, source=None)
    assert found["address"] == "서울특별시 종로구 시험로 1" and found["phone"] == "02-000-0000"
    assert found["hours_text"] == "월 11:00~22:00(라스트오더 21:00)" and found["hours_label"] == "요식 원장"
    assert found["source"].startswith("요식 원장")


# ── 활동 장소 — 관광공사 목록 · 요일별 운영시간 · 1분 작업이 채우기 (2026-09-29 ui 세션 지적) ─────────────
def test_an_activity_gets_its_address_from_the_tour_catalog_and_hours_by_weekday():
    """장소 행에는 관광공사 식별자·운영시간만 있고 주소는 목록 표에만 있다 — 둘을 합쳐 보인다(경복궁 · 창덕궁이 비어 왔다)."""
    tenant = "pinfo_" + uuid4().hex[:8]
    content_id = "t" + uuid4().hex[:10]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO place_catalog (tenant_id, source, content_id, content_type_id, title, address, "
                    "latitude, longitude, raw_json) VALUES (%s,'tour_api',%s,'12','시험 궁','서울특별시 종로구 시험로 99',"
                    "37.58,126.99,%s)", (tenant, content_id, '{"addr2": "(와룡동)", "tel": ""}'))
    place = {"place_id": uuid4(), "name": "시험 궁", "latitude": 37.58, "longitude": 126.99,
             "attributes": {"source": "tour_api", "source_content_id": content_id,
                            "hours_week": {"mon": "closed", "tue": {"open": "09:00", "close": "17:30",
                                                                     "last_entry": "16:30"}},
                            "hours_read": {"source": "tour_api", "quotes": ["09:00~17:30 (입장 마감 16:30)"],
                                           "conditions": ["매주 월요일"]}}}
    try:
        with get_connection() as conn:
            info = place_info(conn, tenant, place)
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM place_catalog WHERE tenant_id=%s", (tenant,))
    assert info["address"] == "서울특별시 종로구 시험로 99 (와룡동)" and info["source_note"] == "ⓒ한국관광공사"
    assert info["hours"][0] == {"day": "월", "weekday": 1, "last_order": None, "open": None, "close": None,
                                "last_entry": None, "closed": True}
    assert info["hours"][1]["last_entry"] == "16:30" and info["hours_source"] == ["tour_api"]
    assert info["hours_text"] == ["09:00~17:30 (입장 마감 16:30)"] and info["hours_conditions"] == ["매주 월요일"]


class _TourStub:
    """관광공사 모양의 고정 답 — 운영정보 한 곳만 안다(자동 시험용, 실제 호출 없음)."""

    def __init__(self, content_id: str) -> None:
        self.content_id, self.calls = content_id, []

    def operating(self, content_id, type_id):
        self.calls.append(content_id)
        if content_id != self.content_id:
            return None
        return {"usetime_text": "09:00~18:00<br>입장 마감 17:00", "restdate_text": "매주 화요일",
                "info_phone": "02-000-1111"}


def test_the_minute_job_reads_hours_and_phone_once_for_places_in_a_live_trip():
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
    from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
    from app.domains.travel_ops.components.places.place_info import fill_missing_facts

    tenant = "pfill_" + uuid4().hex[:8]
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    content_id = "f" + uuid4().hex[:10]
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,'place facts')", (tenant,))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') RETURNING customer_id", (tenant,))
            customer = cur.fetchone()[0]
            cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                        "VALUES (%s,'채움 궁','activity',37.58,126.99,false,%s) RETURNING place_id",
                        (tenant, '{"source": "tour_api", "source_content_id": "%s", "source_content_type_id": "12"}'
                         % content_id))
            place_id = cur.fetchone()[0]
        start = now + timedelta(hours=2)
        with conn.transaction():
            TripStore(tenant).create_trip(conn, customer_id=customer, title="t", locale="ko", party_size=1,
                                          items=[Item(item_id=uuid4(), seq=1, kind="activity", title="채움 궁 관람",
                                                      place_id=place_id, starts_at=start,
                                                      ends_at=start + timedelta(hours=1), detail={})],
                                          constraints={})
    try:
        stub = _TourStub(content_id)
        with get_connection() as conn:
            first = fill_missing_facts(conn, tenant, source=stub, chat=None, now=now)
            second = fill_missing_facts(conn, tenant, source=stub, chat=None, now=now)
            cur = conn.cursor()
            cur.execute("SELECT attributes FROM places WHERE tenant_id=%s AND place_id=%s", (tenant, place_id))
            attributes = cur.fetchone()[0]
        assert (first["asked"], first["read"], first["phone"]) == (1, 1, 1) and second["asked"] == 0   # 한 번만 읽는다
        assert stub.calls == [content_id]
        assert attributes["phone"] == "02-000-1111" and attributes["hours_week"]["tue"] == "closed"
        assert attributes["hours_origin"]["restdate"] == "매주 화요일"
    finally:
        cleanup_tenant(tenant)



class _NoTour:
    """관광공사 모양 — 이름으로 못 찾는다. 구글이 붙어 있어도 부르면 안 된다(자동 시험용 고정 답, 실제 호출 없음)."""

    def __init__(self) -> None:
        self.hours_fallback = self

    def operating(self, *_):
        return None

    def find(self, *_, **__):
        return None

    def week_text(self, **_):
        raise AssertionError("채팅이 구글을 불렀다")


def test_the_chat_never_calls_google_even_when_the_hours_are_unknown(ledger_place):
    """`[2026-09-29 사용자 결정]` 구글 호출은 새벽 3시 확인 창에 몰아서만 — 채팅 답은 원장 · 관광공사까지만 본다."""
    from app.domains.travel_ops.components.conversation.trip_facts import look_up_place

    place = {"place_id": uuid4(), "name": "시험 한식당", "kind": "dining", "latitude": 37.57, "longitude": 126.98,
             "attributes": {"dining_place_uid": ledger_place}}
    found = look_up_place(place, _NoTour())
    assert found["address"] == "서울특별시 종로구 시험로 1"
