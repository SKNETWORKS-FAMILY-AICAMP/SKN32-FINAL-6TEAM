"""SNS에서 분리해 읽은 상호·지역·지점은 각각의 검색 근거로 쓴다."""
from datetime import datetime
from contextlib import nullcontext
import json
import math
import re
import sqlite3
import unicodedata

import pytest
from psycopg.errors import UndefinedTable

from app.domains.travel_ops.components.intake import areas
from app.domains.travel_ops.components.intake import candidates as c
from app.domains.travel_ops.components.places import catalog_pool


NOW = datetime.fromisoformat("2026-10-15T09:00:00+09:00")
SEONGSU = areas.Area("성수", "hub", 37.544, 127.055, 1500)
REAL_LEDGER_PLACES = c._ledger_places


class Catalog:
    """이름 ILIKE만 수행하는 DB 경계. 지역을 상호에 붙이면 실제처럼 누락된다."""

    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, args):
        assert "FROM place_catalog" in sql
        self.name = args[1].strip("%")

    def fetchall(self):
        return [row for row in self.rows if self.name.casefold() in row[2].casefold()]


class Kakao:
    def __init__(self, hits=()):
        self.hits = list(hits)
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return self.hits


@pytest.fixture
def search_context(monkeypatch):
    # 운영시간 조회는 별도 DB 경계이며 이 시험의 이름/지역 검색 판정과 무관하다.
    monkeypatch.setattr(catalog_pool, "reuse_hours", lambda *a: None)
    monkeypatch.setattr(c, "_ledger_places", lambda *a, **kw: [])
    monkeypatch.setattr(c, "assess", lambda *a, **kw: {
        "rows": [], "fits": True, "status": "ok", "slack": {"before": None, "after": None}, "estimated": False,
    })
    monkeypatch.setattr(areas, "areas_for", lambda *a: areas.AreaIndex({"성수": SEONGSU}))
    item = {"id": "0-0", "date": "2026-10-16", "starts_at": "12:00", "ends_at": "13:00",
            "kind": "dining", "parts": {}, "place": None}
    return {"tenant_id": "probe", "review": {"items": [item]}, "item": item, "now": NOW}


def test_separate_name_hint_retains_catalog_row_with_area_in_external_query(search_context):
    conn = Catalog([("1", "39", "가을식당", "서울 성동구 성수동1가", 37.544, 127.055)])
    kakao = Kakao()

    result = c.search(conn, **search_context, query="가을식당 성수", name_hint="가을식당", area_hint="성수", kakao=kakao)

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]
    assert result["query"] == "가을식당 성수"
    assert kakao.calls[0][0] == "가을식당 성수"
    assert kakao.calls[0][1]["near"] == (37.544, 127.055)


def test_area_hint_excludes_another_branch_instead_of_nearer_schedule_area(search_context):
    conn = Catalog([
        ("1", "39", "가을식당 성수점", "서울 성동구 성수동1가", 37.544, 127.055),
        ("2", "39", "가을식당 홍대점", "서울 마포구 서교동", 37.556, 126.924),
    ])

    result = c.search(conn, **search_context, query="가을식당 성수", name_hint="가을식당", area_hint="성수")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]
    assert "area_mismatch" in result["notes"]


def test_unknown_area_requires_address_evidence_not_a_restaurant_name(search_context, monkeypatch):
    monkeypatch.setattr(areas, "areas_for", lambda *a: areas.AreaIndex())
    conn = Catalog([
        ("1", "39", "가을식당", "서울 중구 새동네 12", 37.56, 126.99),
        ("2", "39", "새동네 가을식당", None, 37.57, 126.98),
    ])

    result = c.search(conn, **search_context, query="가을식당 새동네", name_hint="가을식당", area_hint="새동네")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]
    assert "area_unverified" in result["notes"]


def test_branch_hint_keeps_unlabelled_catalog_row_for_identity_check(search_context):
    conn = Catalog([("1", "39", "가을식당", "서울 성동구 성수동1가", 37.544, 127.055)])

    result = c.search(conn, **search_context, query="가을식당 본점 성수", name_hint="가을식당",
                      branch_hint="본점", area_hint="성수")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]


def test_branch_hint_ranks_the_named_branch_without_picking_or_removing_others(search_context):
    conn = Catalog([
        ("1", "39", "가을식당", "서울 성동구 성수동1가", 37.544, 127.055),
        ("2", "39", "가을식당 본점", "서울 성동구 성수동1가", 37.545, 127.055),
    ])

    result = c.search(conn, **search_context, query="가을식당 본점 성수", name_hint="가을식당",
                      branch_hint="본점", area_hint="성수")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:2", "tour:1"]


def test_search_without_structured_hints_preserves_the_existing_name_query(search_context):
    conn = Catalog([("1", "39", "가을식당", "서울 성동구 성수동1가", 37.544, 127.055)])

    result = c.search(conn, **search_context, query="가을식당")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]
    assert result["query"] == "가을식당" and result["notes"] == []


@pytest.mark.parametrize("query", ["우래옥 서울", "서울 우래옥"])
def test_web_query_can_separate_explicit_city_after_full_name_miss(search_context, query):
    conn = Catalog([("1", "39", "우래옥", "서울 중구 창경궁로 62-29", 37.569, 126.999)])

    result = c.search(conn, **search_context, query=query)

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]
    assert result["query"] == query


def test_web_query_preserves_an_exact_name_that_contains_a_city_token(search_context):
    conn = Catalog([("1", "39", "서울 식당", "서울 성동구 성수동1가", 37.544, 127.055),
                    ("2", "39", "식당", "서울 성동구 성수동1가", 37.544, 127.055)])

    result = c.search(conn, **search_context, query="서울 식당")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]


def test_web_query_separates_only_a_known_area_at_the_edge(search_context):
    conn = Catalog([("1", "39", "가을식당", "서울 성동구 성수동1가", 37.544, 127.055)])

    result = c.search(conn, **search_context, query="성수 가을식당")
    ambiguous = c.search(conn, **search_context, query="가을 식당")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:1"]
    assert ambiguous["results"] == []


class SearchStore:
    """실제 후보 SQL을 메모리 DB에서 실행한다. PostgreSQL 문법만 SQLite로 바꾼다."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.create_function("square", 1, lambda value: value * value)
        for name in ("sin", "cos", "radians"):
            self.db.create_function(name, 1, getattr(math, name))
        self.db.create_function("power", 2, pow)
        self.db.create_function("nfkc", 1, lambda value: unicodedata.normalize("NFKC", value))
        self.db.create_function("translate", 3, lambda value, chars, replacement:
                                value.translate(str.maketrans("", "", chars)))
        self.db.create_function("regexp_replace", 4, lambda value, pattern, replacement, flags:
                                re.sub(pattern.replace("[[:space:]", r"[\s"), replacement, value))
        self.db.execute("CREATE TABLE places (place_id TEXT, tenant_id TEXT, source_name TEXT, trip_scope TEXT, "
                        "kind TEXT, name TEXT, latitude REAL, longitude REAL, attributes TEXT)")
        self.db.execute("CREATE TABLE place_catalog (content_id TEXT, content_type_id TEXT, tenant_id TEXT, "
                        "source TEXT, title TEXT, address TEXT, latitude REAL, longitude REAL)")
        self.db.execute("ATTACH DATABASE ':memory:' AS dining")
        self.db.execute("CREATE TABLE dining.dn_place (place_uid TEXT, road_address TEXT, category TEXT)")

    def add_place(self, ident, name, lat, lon, *, tenant="probe", address="서울 중구 창경궁로 62-29", ledger_address=False):
        attributes = {"address": address}
        if ledger_address:
            attributes = {"dining_place_uid": ident}
            self.db.execute("INSERT INTO dining.dn_place VALUES (?,?,?)", (ident, address, "한식"))
        self.db.execute("INSERT INTO places VALUES (?,?,?,NULL,?,?,?,?,?)",
                        (ident, tenant, "dining_ledger", "dining", name, lat, lon, json.dumps(attributes)))

    def add_catalog(self, ident, name, lat, lon, address):
        self.db.execute("INSERT INTO place_catalog VALUES (?,?,?,?,?,?,?,?)",
                        (ident, "39", "probe", "tour_api", name, address, lat, lon))

    def transaction(self):
        return nullcontext()

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, args):
        tenants, *rest = args
        sql = re.sub(r"(\w+(?:::\w+)?) = ANY\(%s\)",
                     lambda match: match[1] + " IN (" + ",".join("?" for _ in tenants) + ")", sql)
        sql = sql.replace("::text", "").replace("normalize(", "nfkc(").replace(", NFKC)", ")")
        sql = sql.replace("(latitude - %s)^2", "square(latitude - %s)")
        sql = sql.replace("((longitude - %s) * %s)^2", "square((longitude - %s) * %s)")
        sql = sql.replace("((longitude - %s) * 0.8)^2", "square((longitude - %s) * 0.8)")
        try:
            self.result = self.db.execute(sql.replace("ILIKE", "LIKE").replace("%s", "?"), [*tenants, *rest])
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                raise UndefinedTable(str(exc)) from exc
            raise

    def fetchall(self):
        return self.result.fetchall()


@pytest.fixture
def ledger_store(search_context, monkeypatch):
    monkeypatch.setattr(c, "_ledger_places", REAL_LEDGER_PLACES)
    search_context["item"]["place"] = c._place("기존 식당", 37.498, 127.028, "places", kind="dining")
    conn = SearchStore()
    yield conn
    conn.db.close()


@pytest.mark.parametrize("query,hints", [
    ("우래옥 서울", {"name_hint": "우래옥", "area_hint": "서울"}),
    ("우래옥 서울", {}),
    ("서울 우래옥", {}),
    ("우래옥", {}),
])
def test_named_ledger_search_covers_seoul_beyond_five_km_and_keeps_scope(ledger_store, search_context, query, hints):
    ledger_store.add_place("far", "우래옥", 37.569, 126.999)
    ledger_store.add_place("private", "우래옥", 37.569, 126.999, tenant="__other_private_tenant__")
    ledger_store.add_place("outside", "우래옥", 36.3, 127.1)

    result = c.search(ledger_store, **search_context, query=query, **hints)

    assert [row["place"]["ref"] for row in result["results"]] == ["place:far"]
    assert result["results"][0]["distance_m"] > 5000


def test_named_ledger_search_does_not_need_an_existing_itinerary_reference(ledger_store, search_context):
    ledger_store.add_place("far", "우래옥", 37.569, 126.999)
    search_context["item"]["place"] = None

    result = c.search(ledger_store, **search_context, query="우래옥 서울", name_hint="우래옥", area_hint="서울")

    assert [row["place"]["ref"] for row in result["results"]] == ["place:far"]


def test_exact_ledger_name_survives_sql_and_external_candidate_limits(ledger_store, search_context):
    for index in range(40):
        ledger_store.add_place(f"prefix{index}", f"우래옥 지점{index}", 37.499, 127.029)
    ledger_store.add_place("far", "우래옥", 37.569, 126.999)
    kakao = Kakao([{"id": str(index), "name": f"다른식당{index}", "latitude": 37.499, "longitude": 127.029,
                    "address": "서울 강남구 강남대로", "category_group": "FD6"} for index in range(45)])

    result = c.search(ledger_store, **search_context, query="우래옥 서울", name_hint="우래옥", area_hint="서울",
                      kakao=kakao, limit=1)

    assert [row["place"]["ref"] for row in result["results"]] == ["place:far"]


def test_nearby_ledger_alternatives_keep_the_existing_radius(ledger_store):
    ledger_store.add_place("far", "우래옥", 37.569, 126.999)
    ledger_store.add_place("near", "동네식당", 37.499, 127.029)

    found = c._ledger_places(ledger_store, "probe", (37.498, 127.028))

    assert [place["ref"] for place in found] == ["place:near"]


def test_unknown_area_filters_catalog_before_its_ten_result_limit(ledger_store, search_context):
    for index in range(10):
        ledger_store.add_catalog(str(index), f"가을식당 강남{index}점", 37.499, 127.029, "서울 강남구 강남대로")
    ledger_store.add_catalog("wanted", "가을식당 새동네점", 37.569, 126.999, "서울 중구 새 동네 12")

    result = c.search(ledger_store, **search_context, query="가을식당 새동네", name_hint="가을식당", area_hint="새동네")

    assert [row["place"]["ref"] for row in result["results"]] == ["tour:wanted"]


def test_unknown_area_filters_ledger_road_address_before_its_result_limit(ledger_store, search_context):
    for index in range(30):
        ledger_store.add_place(str(index), f"가을식당 강남{index}점", 37.499, 127.029, address="서울 강남구 강남대로",
                               ledger_address=True)
    ledger_store.add_place("wanted", "가을식당 새동네점", 37.569, 126.999, address="서울 중구 새 동네 12", ledger_address=True)

    result = c.search(ledger_store, **search_context, query="가을식당 새동네", name_hint="가을식당", area_hint="새동네")

    assert [row["place"]["ref"] for row in result["results"]] == ["place:wanted"]
    assert result["results"][0]["place"]["address"] == "서울 중구 새 동네 12"


@pytest.mark.parametrize("source", ["catalog", "ledger"])
def test_known_area_filters_coordinates_before_name_result_limits(ledger_store, source):
    add = ledger_store.add_catalog if source == "catalog" else ledger_store.add_place
    for index in range(30):
        add(str(index), "가을식당", 37.499, 127.029, address="서울 성동구 성수동")
    add("wanted", "가을식당", 37.544, 127.055, address="서울 성동구 성수동")
    hints = {"area_hint": "성수", "area": SEONGSU.as_dict()}

    if source == "catalog":
        found = c._db_places_by_name(ledger_store, "probe", "가을식당", (37.498, 127.028), NOW, **hints)
        assert [place["ref"] for place in found] == ["tour:wanted"]
    else:
        found = c._ledger_places(ledger_store, "probe", (37.498, 127.028), query="가을식당", radius_m=None, **hints)
        assert [place["ref"] for place in found] == ["place:wanted"]


def test_missing_ledger_schema_uses_only_explicit_place_addresses(ledger_store, search_context):
    ledger_store.add_place("known", "가을식당", 37.569, 126.999, address="서울 중구 새 동네 12")
    ledger_store.add_place("unknown", "가을식당", 37.570, 126.999, address=None)
    ledger_store.db.execute("DROP TABLE dining.dn_place")

    result = c.search(ledger_store, **search_context, query="가을식당 새동네", name_hint="가을식당", area_hint="새동네")

    assert [row["place"]["ref"] for row in result["results"]] == ["place:known"]


@pytest.mark.parametrize("source", ["catalog", "ledger"])
def test_named_branch_survives_forty_nearer_branches_and_keeps_unlabelled_rows(ledger_store, search_context, source):
    add = ledger_store.add_catalog if source == "catalog" else ledger_store.add_place
    for index in range(40):
        add(str(index), f"가을식당 강남{index}점", 37.499, 127.029, address="서울 강남구 강남대로")
    add("unlabelled", "가을식당", 37.4981, 127.0281, address="서울 강남구 강남대로")
    add("wanted", "가을식당 본점", 37.569, 126.999, address="서울 중구 창경궁로 62-29")

    result = c.search(ledger_store, **search_context, query="가을식당 본점 서울", name_hint="가을식당",
                      area_hint="서울", branch_hint="본점", limit=2)

    prefix = "tour:" if source == "catalog" else "place:"
    assert [row["place"]["ref"] for row in result["results"]] == [prefix + "wanted", prefix + "unlabelled"]


@pytest.mark.parametrize("source", ["catalog", "ledger"])
def test_unknown_neighbourhood_keeps_explicit_parenthesized_address_evidence(ledger_store, search_context, source):
    add = ledger_store.add_catalog if source == "catalog" else ledger_store.add_place
    add("wanted", "우래옥", 37.569, 126.999, address="서울 중구 창경궁로 62-29 (주교동)")

    result = c.search(ledger_store, **search_context, query="우래옥 주교동", name_hint="우래옥", area_hint="주교동")

    expected = "tour:wanted" if source == "catalog" else "place:wanted"
    assert [row["place"]["ref"] for row in result["results"]] == [expected]


@pytest.mark.parametrize("source", ["catalog", "ledger"])
def test_branch_word_inside_brand_is_not_mistaken_for_its_branch_suffix(ledger_store, search_context, source):
    add = ledger_store.add_catalog if source == "catalog" else ledger_store.add_place
    for index in range(40):
        add(str(index), f"본점식당 강남{index}점", 37.499, 127.029, address="서울 강남구 강남대로")
    add("unlabelled", "본점식당", 37.4981, 127.0281, address="서울 강남구 강남대로")
    add("wanted", "본점식당 본점", 37.569, 126.999, address="서울 중구 창경궁로 62-29")

    result = c.search(ledger_store, **search_context, query="본점식당 본점 서울", name_hint="본점식당",
                      area_hint="서울", branch_hint="본점", limit=2)

    prefix = "tour:" if source == "catalog" else "place:"
    assert [row["place"]["ref"] for row in result["results"]] == [prefix + "wanted", prefix + "unlabelled"]
