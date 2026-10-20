"""공개 사실 식당과 실제 원장·영업 판정·TripDesk 저장을 합성 전용 DB에서 검증한다."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import database_dsn, get_connection
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.itinerary.itinerary_changes import ALTERNATE_RADII_M, NoChange, plan_fresh_alternate
from app.domains.travel_ops.instances.dining.ledger import dining_state, nearby_shops

pytestmark = pytest.mark.skipif(not os.environ.get("DINING_RADIUS_SYNTHETIC_DATABASE_URL"),
                               reason="requires explicit isolated synthetic database and public fact fixture")


@pytest.fixture(autouse=True)
def guard():
    expected = os.environ["DINING_RADIUS_SYNTHETIC_DATABASE_URL"]
    parsed = urlsplit(expected)
    assert database_dsn() == expected
    assert (parsed.hostname, parsed.port, parsed.path, parsed.username) == (
        "127.0.0.1", 15544, "/semantic_synthetic", "semantic_test")
    with get_connection() as conn:
        assert conn.execute("SELECT current_database(),current_user").fetchone() == ("semantic_synthetic", "semantic_test")
        assert conn.execute("SELECT owner FROM semantic_test_isolation_guard").fetchone() == ("semantic-contract-repair",)


@pytest.fixture
def public_shop():
    facts = json.loads(Path(os.environ["DINING_ORIGIN_FACTS_PATH"]).read_text(encoding="utf8"))
    fact = facts["nearest_not_closed"]
    assert facts["origin"] == {"latitude": 37.5603, "longitude": 127.1291}
    assert fact["record_status"] != "closed" and not fact["is_synthetic"]
    uid, load, record = uuid4(), uuid4(), uuid4()
    with get_connection() as conn, conn.transaction():
        conn.execute("INSERT INTO dining.dn_load_meta(load_id,source_code,fetched_at,schema_version,scope,row_count,status) "
                     "VALUES(%s,'tourapi_kor_food',%s,'public-fact-slot-verification','isolated synthetic DB only',1,'verified')",
                     (load, fact["fetched_at"]))
        conn.execute("INSERT INTO dining.dn_place(place_uid,name_ko,lat,lng,area,coord_source,record_status,is_synthetic,category,category_method) "
                     "VALUES(%s,%s,%s,%s,%s,'tourapi_kor_food',%s,false,%s,%s)",
                     (uid, fact["name"], fact["latitude"], fact["longitude"], fact["area"], fact["record_status"], fact["category"], fact["category_method"]))
        conn.execute("INSERT INTO dining.dn_source_record(record_id,load_id,source_code,external_id,place_uid,match_status,raw_json) "
                     "VALUES(%s,%s,'tourapi_kor_food',%s,%s,'confirmed',%s)",
                     (record, load, fact["content_id"], uid, json.dumps({"fixture_source_sha256": facts["csv_sha256"]})))
        for weekday, rule in fact["rules"].items():
            rule_id = uuid4()
            conn.execute("INSERT INTO dining.dn_hours_rule(rule_id,place_uid,source_code,record_id,rule_kind,weekday,coverage,break_state,source_text,extract_method,rules_version,valid_from) "
                         "VALUES(%s,%s,'tourapi_kor_food',%s,'weekly',%s,%s,%s,%s,'regex','public-fact-fixture','2026-09-21')",
                         (rule_id, uid, record, int(weekday), rule["coverage"], rule["break_state"], fact["hours_text"]))
            for interval in rule["intervals"]:
                conn.execute("INSERT INTO dining.dn_hours_interval(rule_id,seq,open_min,close_min,last_order_min,last_order_state) VALUES(%s,%s,%s,%s,%s,%s)",
                             (rule_id, interval["seq"], interval["open_min"], interval["close_min"], interval["last_order_min"], interval["last_order_state"]))
    return facts


def make_trip(facts, *, hour=12):
    tenant = "radius_test_" + uuid4().hex[:12]
    customer = uuid4()
    store = TripStore(tenant)
    at = datetime(2026, 10, 18, hour, tzinfo=ZoneInfo("Asia/Seoul"))
    with get_connection() as conn, conn.transaction():
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'synthetic radius verification')", (tenant,))
        conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,'synthetic-agent')", (customer, tenant))
        origin_id = conn.execute("INSERT INTO places(tenant_id,name,kind,latitude,longitude,attributes) VALUES(%s,'합성 기준 위치','activity',%s,%s,'{}') RETURNING place_id",
                                 (tenant, facts["origin"]["latitude"], facts["origin"]["longitude"])).fetchone()[0]
        old_id = conn.execute("INSERT INTO places(tenant_id,name,kind,latitude,longitude,attributes) VALUES(%s,'합성 원래 점심','dining',37.57,126.98,%s) RETURNING place_id",
                              (tenant, json.dumps({"hours": ["08:00", "22:00"]}))).fetchone()[0]
        stop = Item(item_id=uuid4(), seq=1, kind="dining", title="합성 원래 점심", place_id=old_id,
                    starts_at=at, ends_at=at+timedelta(hours=1))
        trip_id, _ = store.create_trip(conn, customer_id=customer, title="synthetic radius only", locale="ko", party_size=2, items=[stop], constraints={})
        trip, items = store.latest(conn, trip_id)
        places = store.places(conn, trip_id)
        origin = next(p for p in places if p["place_id"] == str(origin_id))
    desk = TripDesk(store=store, connection_factory=get_connection)
    return SimpleNamespace(store=store, trip_id=trip_id, trip=trip, items=items, places=places, origin=origin, desk=desk)


def test_actual_public_shop_outside_default_radius_is_loaded_and_selected_by_shared_wide_radius(public_shop):
    case = make_trip(public_shop)
    with get_connection() as conn:
        assert nearby_shops(conn, case.store.tenant_id, [(case.origin["latitude"], case.origin["longitude"])], radius_m=min(ALTERNATE_RADII_M["dining"])) == []
    proxy = SimpleNamespace(kind="dining", place=case.origin, starts_at=case.items[0].starts_at, ends_at=case.items[0].ends_at)
    limited = case.desk._add_nearby(case.trip_id, proxy, case.places)
    before = plan_fresh_alternate(trip=case.trip, trip_version=1, base_version=1, items=case.items, places=limited,
        item_id=case.items[0].item_id, message="기준 위치 근처로", request_id=None,
        state_lookup=case.desk._state_lookup(), search_origin=case.origin)
    assert isinstance(before, NoChange) and before.status == "no_alternate"
    result = case.desk.near_alternate(trip_id=case.trip_id, item_id=case.items[0].item_id, base_version=1, origin=case.origin)
    assert result["status"] == "adjusted", result
    with get_connection() as conn:
        trip, items = case.store.latest(conn, case.trip_id)
        [meal] = items
        assert trip["version"] == 2 and meal.title == public_shop["nearest_not_closed"]["name"]
        distance = conn.execute("SELECT dining.distance_m(%s,%s,%s,%s)", (case.origin["latitude"], case.origin["longitude"], meal.place["latitude"], meal.place["longitude"])).fetchone()[0]
        assert 804 < distance < 806 and distance <= max(ALTERNATE_RADII_M["dining"])
        state = dining_state(conn, case.store.tenant_id, meal.place_id, meal.starts_at, meal.ends_at)
        assert state["linked"] and state["open_at_slot"] is True
        assert meal.starts_at.hour >= 10 and meal.ends_at.hour <= 22
    stale = case.desk.near_alternate(trip_id=case.trip_id, item_id=meal.item_id, base_version=1, origin=case.origin)
    assert stale["status"] == "stale"


def test_expanded_origin_search_keeps_real_opening_time_guard(public_shop):
    case = make_trip(public_shop, hour=8)
    result = case.desk.near_alternate(trip_id=case.trip_id, item_id=case.items[0].item_id, base_version=1, origin=case.origin)
    assert result["status"] != "adjusted", result
    with get_connection() as conn:
        trip, items = case.store.latest(conn, case.trip_id)
    assert trip["version"] == 1 and items[0].place_id == case.items[0].place_id
