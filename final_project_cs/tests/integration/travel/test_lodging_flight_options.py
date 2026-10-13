# -*- coding: utf-8 -*-
"""숙소 · 항공 「다른 후보」 — 일정을 바꾸지 않고 묻고, 고르면 바뀐다. `[2026-10-13]`

☆숙소 · 항공 팀(`role-lodging`)은 후보를 항목 상세에 싣는 `itinerary.apply` 를 내서, 후보를 볼 때마다 일정 판이 오르고
  「일정이 바뀌었어요」 알림이 나갔다. 고른 숙소는 장소 표에 없어 `place_id` 가 비어 지도 핀이 없었다.
  이제 식당 · 활동의 「다른 후보」처럼 「선택이 필요해요」 보류 제안을 연다(`options_arguments` → `_ask_options`, 판 그대로).
  고르면 숙소는 숙소 원장이 그 여행 전용 장소로 들여놓고(`pending.choose`) 바뀐다 — 핀이 생긴다.
실제 DB(로컬 개발 DB)에 쓴다 — 전용 테넌트를 만들고 끝나면 지운다. 숙소 원장 표(마이그레이션 240)가 있어야 한다.
"""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.service_bindings import standalone_services
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.domains.travel_ops.components.actions.itinerary_actions import ItineraryApply, options_arguments
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.planning.pending import PendingStore, choose
from app.domains.travel_ops.components.team_hooks import lodging_ledger
from app.domains.travel_ops.instances.lodging import ledger

KST = ZoneInfo("Asia/Seoul")


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2030, 1, day, hour, minute, tzinfo=KST)


def _option(rank, key, name, *, lat=None, lon=None, link=None, starts=None):
    return {"key": key, "rank": rank, "name": name, "place_id": None, "option": None, "option_label": None,
            "starts_at": starts, "ends_at": None, "walk_min": None, "source": "마이리얼트립",
            "price_per_night": 150000 + rank, "latitude": lat, "longitude": lon, "link": link}


def _setup(tenant):
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,'lodging options')", (tenant,))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') RETURNING customer_id", (tenant,))
            customer = cur.fetchone()[0]
            cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                        "VALUES (%s,'기존 호텔','lodging',37.56,126.98,false,%s) RETURNING place_id",
                        (tenant, json.dumps({"district": "중구"})))
            hotel = cur.fetchone()[0]
        store = TripStore(tenant)
        items = [Item(item_id=uuid4(), seq=1, kind="flight", title="김포 → 제주", place_id=None,
                      starts_at=_at(1, 9), ends_at=_at(1, 10, 10), detail={"origin": "GMP", "destination": "CJU"}),
                 Item(item_id=uuid4(), seq=2, kind="lodging", title="기존 호텔", place_id=hotel,
                      starts_at=_at(1, 20), ends_at=_at(2, 9), detail={})]
        with conn.transaction():
            trip_id, _ = store.create_trip(conn, customer_id=customer, title="t", locale="ko", party_size=2,
                                           items=items, constraints={})
    return store, customer, trip_id, items


def _ask(store, customer, trip_id, item, options, *, shown_key=None):
    with get_connection() as conn, conn.transaction():
        return ItineraryApply().apply(conn, tenant_id=store.tenant_id, customer_id=customer, case_id=uuid4(),
                                      arguments=options_arguments(trip_id=trip_id, base_version=1, item_id=item.item_id,
                                                                  options=options, text="고르시면 바꿀게요.",
                                                                  causes=[{"category": "customer_request",
                                                                           "type": "requested_options"}],
                                                                  shown_key=shown_key))


def test_lodging_options_do_not_bump_the_version_and_choosing_adopts_a_place_with_a_pin():
    tenant = "lodgopt_" + uuid4().hex[:8]
    try:
        with standalone_services():
            lodging_ledger.register(remember=ledger.remember_shown, shown=ledger.shown_keys, adopt=ledger.adopt_option,
                                    item_key=ledger.item_key, offers=ledger.shown_offers)
            store, customer, trip_id, items = _setup(tenant)
            stay = items[1]
            key = "lodging:2030-01-01:2030-01-02"
            first = _ask(store, customer, trip_id, stay,
                         [_option(1, "myrealtrip:11", "해밀톤 호텔", lat=37.5345, lon=126.9946, link="https://example.test/11"),
                          _option(2, "myrealtrip:12", "좌표 없는 호텔")], shown_key=key)
            assert first.summary["status"] == "asked" and first.summary["version"] == 1 and first.summary["remembered"] == 2
            assert [m.payload["type"] for m in first.outbox] == ["proposal_request"], "「선택이 필요해요」 — 변경 알림이 아니다"
            # 또 「바꿔 줘」 — 앞 제안은 닫고 새 후보로 연다. 원장에는 둘 다 남는다
            second = _ask(store, customer, trip_id, stay,
                          [_option(1, "myrealtrip:13", "셋째 호텔", lat=37.5600, lon=126.9800),
                           _option(2, "myrealtrip:11", "해밀톤 호텔", lat=37.5345, lon=126.9946, link="https://example.test/11")],
                          shown_key=key)
            with get_connection() as conn:
                trip, _ = store.latest(conn, trip_id)
                assert trip["version"] == 1, "후보를 두 번 보여 줘도 일정 판은 그대로"
                rows = PendingStore(tenant).list(conn, trip_id)
                assert [(r["reason"], r["status"]) for r in rows] == [("requested_options", "open")],                     "제안 자리는 항목 · 판마다 하나 — 같은 자리를 새 후보로 다시 연다"
                assert [o["name"] for o in rows[0]["options_json"]] == ["셋째 호텔", "해밀톤 호텔"]
                assert second.summary["proposal_id"] == first.summary["proposal_id"]
                assert second.outbox[0].dedupe_key != first.outbox[0].dedupe_key, "새 후보면 알림도 새로"
                assert [o["name"] for o in ledger.shown_offers(conn, tenant, trip_id, key)] == \
                    ["해밀톤 호텔", "좌표 없는 호텔", "셋째 호텔"]
                places = {str(p["place_id"]): p for p in store.places(conn, trip_id)}
                with conn.transaction():
                    done = choose(conn=conn, store=store, pending=PendingStore(tenant), trip_id=trip_id,
                                  proposal_id=second.summary["proposal_id"], key="myrealtrip:11", by="c",
                                  places_by_id=places, check=None)
                assert done["status"] == "chosen" and done["version"] == 2
                _, after = store.latest(conn, trip_id)
                with conn.cursor() as cur:
                    cur.execute("SELECT offer_key FROM lg_core_place_link WHERE tenant_id=%s", (tenant,))
                    linked = [row[0] for row in cur.fetchall()]
            new = next(i for i in after if i.kind == "lodging")
            assert new.title == "해밀톤 호텔" and new.place is not None and new.place["name"] == "해밀톤 호텔", "고른 숙소가 장소로 들어왔다 — 지도 핀"
            assert (new.place["latitude"], new.place["longitude"]) == (37.5345, 126.9946)
            assert new.detail["chosen"]["link"] == "https://example.test/11" and new.detail["booked"] is False
            assert linked == ["myrealtrip:11"]
    finally:
        lodging_ledger.clear()
        cleanup_tenant(tenant)


def test_a_lodging_option_without_coordinates_drops_the_old_pin_instead_of_keeping_it():
    tenant = "lodgopt_" + uuid4().hex[:8]
    try:
        with standalone_services():
            lodging_ledger.register(remember=ledger.remember_shown, shown=ledger.shown_keys, adopt=ledger.adopt_option,
                                    item_key=ledger.item_key, offers=ledger.shown_offers)
            store, customer, trip_id, items = _setup(tenant)
            asked = _ask(store, customer, trip_id, items[1], [_option(1, "myrealtrip:12", "좌표 없는 호텔")])
            with get_connection() as conn:
                places = {str(p["place_id"]): p for p in store.places(conn, trip_id)}
                with conn.transaction():
                    done = choose(conn=conn, store=store, pending=PendingStore(tenant), trip_id=trip_id,
                                  proposal_id=asked.summary["proposal_id"], key="myrealtrip:12", by="c",
                                  places_by_id=places, check=None)
                _, after = store.latest(conn, trip_id)
            new = next(i for i in after if i.kind == "lodging")
            assert done["status"] == "chosen" and new.title == "좌표 없는 호텔"
            assert new.place_id is None, "좌표를 모르면 핀을 지어내지 않는다 — 원래 호텔 핀도 남기지 않는다"
    finally:
        lodging_ledger.clear()
        cleanup_tenant(tenant)


def test_flight_options_ask_first_and_choosing_moves_the_departure():
    tenant = "lodgopt_" + uuid4().hex[:8]
    try:
        with standalone_services():
            store, customer, trip_id, items = _setup(tenant)
            leg = items[0]
            option = {**_option(1, "제주항공 7C101 2030-01-01 11:00", "제주항공 7C101 11:00", starts=_at(1, 11).isoformat()),
                      "link": "https://example.test/f"}
            asked = _ask(store, customer, trip_id, leg, [option])
            with get_connection() as conn:
                trip, _ = store.latest(conn, trip_id)
                assert trip["version"] == 1
                with conn.transaction():
                    done = choose(conn=conn, store=store, pending=PendingStore(tenant), trip_id=trip_id,
                                  proposal_id=asked.summary["proposal_id"], key=option["key"], by="c",
                                  places_by_id={}, check=None)
                _, after = store.latest(conn, trip_id)
            new = next(i for i in after if i.kind == "flight")
            assert done["status"] == "chosen" and new.title == "김포 → 제주", "항공 항목 제목은 노선 그대로"
            assert new.starts_at.astimezone(KST).strftime("%H:%M") == "11:00" and new.ends_at is None
            assert new.detail["key"] == option["key"] and new.detail["chosen"]["name"] == "제주항공 7C101 11:00"
    finally:
        cleanup_tenant(tenant)
