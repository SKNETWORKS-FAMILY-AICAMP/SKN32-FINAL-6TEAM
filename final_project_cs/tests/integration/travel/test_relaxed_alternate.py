# -*- coding: utf-8 -*-
"""조건을 풀어 찾은 안 — **묻고**, 고르면 그 시각 · 그 장소로 바뀐다. `[2026-09-29 사용자 지적 — ui 세션 전달]`

☆「08:00에 갈 수 있는 식당이 3km 안에 없어요」로 끝나면 고객이 할 수 있는 것이 없었다. 늦추면 되는 안을 「선택이 필요해요」
  제안(`pending_changes`, 이유 `relaxed`)으로 보내고, 고르면 기존 「다른 안으로」 경로로 적용한다. 답이 없으면 그대로.
"""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.modules.travel_ops.itinerary import Item, TripStore
from app.modules.travel_ops.pending import PendingStore, choose
from app.modules.travel_ops.trip_desk import TripDesk

KST = ZoneInfo("Asia/Seoul")


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2030, 1, 1, hour, minute, tzinfo=KST)


def test_asking_for_another_breakfast_offers_a_later_time_and_choosing_applies_it():
    tenant = "relax_" + uuid4().hex[:8]
    try:
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,'relaxed')", (tenant,))
                cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') RETURNING customer_id", (tenant,))
                customer = cur.fetchone()[0]
                ids = {}
                for key, name, kind, lat, lon, hours in (
                        ("home", "원래 아침집", "dining", 37.5700, 126.9800, ["07:00", "10:00"]),
                        ("nine", "9시에 여는 집", "dining", 37.5705, 126.9805, ["09:00", "22:00"]),
                        ("palace", "경복궁", "activity", 37.5760, 126.9767, ["09:00", "18:00"])):
                    cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                                "VALUES (%s,%s,%s,%s,%s,false,%s) RETURNING place_id",
                                (tenant, name, kind, lat, lon, json.dumps({"hours": hours, "payment": ["card"]})))
                    ids[key] = cur.fetchone()[0]
            store = TripStore(tenant)
            items = [Item(item_id=uuid4(), seq=1, kind="dining", title="원래 아침집", place_id=ids["home"],
                          starts_at=_at(8), ends_at=_at(9), detail={}),
                     # ★`[2026-09-29 ui 세션 지적]` 뒤따르는 이동(09:00 출발) — 전에는 늦춘 안을 고르면 이것과 겹쳐 422 였다
                     Item(item_id=uuid4(), seq=2, kind="mobility", title="원래 아침집 → 경복궁", place_id=None,
                          starts_at=_at(9), ends_at=_at(9, 30), detail={}),
                     Item(item_id=uuid4(), seq=3, kind="activity", title="경복궁", place_id=ids["palace"],
                          starts_at=_at(11), ends_at=_at(12), detail={})]
            with conn.transaction():
                trip_id, _ = store.create_trip(conn, customer_id=customer, title="t", locale="ko", party_size=2,
                                               items=items, constraints={})
        desk = TripDesk(store=store, connection_factory=get_connection, dining_ledger=False)
        asked = desk.fresh_alternate(trip_id=trip_id, item_id=items[0].item_id, base_version=1,
                                     message="첫 식당 다른 걸로 바꿔", request_id="r1")
        assert asked["status"] == "asked" and "09:00으로 늦추면 9시에 여는 집" in asked["text"], asked
        with get_connection() as conn:
            trip, now_items = store.latest(conn, trip_id)
            assert trip["version"] == 1                                         # 묻기만 했다 — 안 바꿨다
            open_ = PendingStore(tenant).list(conn, trip_id, only_open=True)
            assert [p["reason"] for p in open_] == ["relaxed"]
            places = {str(p["place_id"]): p for p in store.places(conn)}
            with conn.transaction():
                done = choose(conn=conn, store=store, pending=PendingStore(tenant), trip_id=trip_id,
                              proposal_id=open_[0]["proposal_id"], key=open_[0]["options_json"][0]["key"], by="c",
                              places_by_id=places, check=None)
            assert done["status"] == "chosen"
            _, after = store.latest(conn, trip_id)
        breakfast = next(i for i in after if i.kind == "dining")
        assert (breakfast.place["name"], breakfast.starts_at.astimezone(KST).strftime("%H:%M")) == ("9시에 여는 집", "09:00")
        move = next(i for i in after if i.kind == "mobility")
        assert move.starts_at.astimezone(KST).strftime("%H:%M") >= "10:00"            # 이동도 새 끝 시각 뒤로 밀렸다
        assert move.ends_at <= next(i for i in after if i.kind == "activity").starts_at
    finally:
        cleanup_tenant(tenant)
