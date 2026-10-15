# -*- coding: utf-8 -*-
"""숙소 · 항공 원장(`instances/lodging/ledger.py`)과 꽂는 자리(`components/team_hooks/lodging_ledger.py`). DB 없이 — 연결 · 저장소는 가짜다. `[2026-10-12]`"""
from __future__ import annotations

from app.domains.travel_ops.components.team_hooks import lodging_ledger as hook
from app.domains.travel_ops.instances.lodging import ledger

TRIP = "11111111-1111-4111-8111-111111111111"


class FakeCursor:
    def __init__(self, log, rows=()):
        self.log, self.rows, self.rowcount = log, list(rows), 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.log.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, rows=()):
        self.log, self.rows = [], rows

    def cursor(self):
        return FakeCursor(self.log, self.rows)


class FakeStore:
    tenant_id = "t"

    def __init__(self):
        self.adopted = []

    def adopt_places(self, conn, trip_id, rows):
        self.adopted.append((trip_id, rows))
        return [{**row, "place_id": "99999999-9999-4999-8999-999999999999", "trip_scope": str(trip_id)} for row in rows]


OPTION = {"key": "google:가까운호텔", "name": "가까운 호텔", "source": "구글 호텔", "price_per_night": 120000.0,
          "latitude": 37.543, "longitude": 126.991, "link": "https://near.example"}


def test_item_key_names_an_item_the_same_across_versions():
    assert ledger.item_key("lodging", {"check_in": "2026-11-06", "check_out": "2026-11-09"}) == "lodging:2026-11-06:2026-11-09"
    assert ledger.item_key("flight", {"origin": "ICN", "destination": "NRT", "depart_date": "2026-11-06"}) == "flight:ICN-NRT:2026-11-06"
    assert ledger.item_key("lodging", {"check_in": "2026-11-06"}) is None


def test_remember_and_read_back_what_was_shown_only_in_our_table():
    conn = FakeConn(rows=[("google:가까운호텔",)])
    ledger.remember_shown(conn, "t", TRIP, "lodging:2026-11-06:2026-11-09", [OPTION], case_id="c1")
    sql, params = conn.log[0]
    assert sql.startswith("INSERT INTO lg_offer_shown") and "ON CONFLICT DO NOTHING" in sql
    assert params == ("t", TRIP, "lodging:2026-11-06:2026-11-09", "google:가까운호텔", "가까운 호텔", "구글 호텔",
                      "https://near.example", 120000.0, "c1")
    assert ledger.shown_keys(conn, "t", TRIP, "lodging:2026-11-06:2026-11-09") == ["google:가까운호텔"]
    assert all("lg_" in sql for sql, _ in conn.log), "코어 표에 직접 쓰지 않는다"


def test_a_chosen_stay_with_coordinates_is_adopted_as_a_trip_place_and_linked():
    conn, store = FakeConn(), FakeStore()
    place = ledger.adopt_option(conn, store, TRIP, OPTION)
    assert place["place_id"] == "99999999-9999-4999-8999-999999999999" and place["trip_scope"] == TRIP
    (trip_id, rows), = store.adopted
    assert rows == [{"name": "가까운 호텔", "kind": "lodging", "latitude": 37.543, "longitude": 126.991,
                     "attributes": {"source": "lodging_ledger", "offer_key": "google:가까운호텔", "provider": "구글 호텔",
                                    "link": "https://near.example"}}], "장소 행은 코어(adopt_places)가 여행 전용으로 만든다"
    sql, params = conn.log[0]
    assert sql.startswith("INSERT INTO lg_core_place_link") and params[:4] == ("t", place["place_id"], TRIP, "google:가까운호텔")


def test_a_stay_without_coordinates_is_not_adopted():
    conn, store = FakeConn(), FakeStore()
    assert ledger.adopt_option(conn, store, TRIP, {**OPTION, "latitude": None}) is None
    assert store.adopted == [] and conn.log == [], "좌표를 지어내지 않는다 — 부르는 쪽은 place_id 를 비운 채로 간다"


def test_the_hook_is_the_old_path_until_registered_and_the_ledger_once_registered():
    hook.clear()
    try:
        assert not hook.is_registered()
        assert hook.remember_shown(FakeConn(), "t", TRIP, "k", [OPTION]) == 0
        assert hook.shown_keys(FakeConn(), "t", TRIP, "k") == []
        assert hook.adopt_option(FakeConn(), FakeStore(), TRIP, OPTION) is None
        assert hook.item_key("lodging", {"check_in": "a", "check_out": "b"}) is None
        hook.register(remember=ledger.remember_shown, shown=ledger.shown_keys, adopt=ledger.adopt_option, item_key=ledger.item_key)
        assert hook.is_registered()
        assert hook.adopt_option(FakeConn(), FakeStore(), TRIP, OPTION)["kind"] == "lodging"
        assert hook.item_key("lodging", {"check_in": "a", "check_out": "b"}) == "lodging:a:b"
    finally:
        hook.clear()

