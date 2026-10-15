"""`read.booking` 이 그 예약이 속한 여행(`trip`)을 붙인다 — `[2026-10-13]` 활동 → 코어 전달 8번 회신.

예약 성립 판정 Case 는 여행을 가리키지 않아 설문을 못 받았다. 도구가 예약 → 여행을 찾아 주면 팀이 `read.itinerary` 로
그 여행의 설문을 읽는다. 실제 DB 로 본다.
  1. 여행 최신 일정판의 항목이 이 예약을 가리키면 그 여행(`itinerary_item`)
  2. 아니면 예약 날짜(서울)가 기간 안에 드는 진행 중 여행이 **딱 하나**일 때 그 여행(`trip_period` — 추정)
  3. 둘 이상이면 고르지 않는다(`ambiguous`), 없으면 `not_linked`
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ReadToolbox, ToolContext

KST = timezone(timedelta(hours=9))
DAY = datetime(2026, 11, 10, 10, 0, tzinfo=KST)


@pytest.fixture()
def world():
    tenant = "bookingtrip_" + uuid4().hex[:10]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "booking trip link"))
        ids = {}
        for name in ("owner", "stranger"):
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id", (tenant, name))
            ids[name] = cur.fetchone()[0]
    yield {"tenant": tenant, **ids}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trips WHERE tenant_id=%s", (tenant,))       # 항목이 예약을 가리키므로 여행 먼저
        cur.execute("DELETE FROM bookings WHERE tenant_id=%s", (tenant,))
    cleanup_tenant(tenant)


def _booking(world, starts_at, customer="owner"):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO bookings (tenant_id,customer_id,booking_no,kind,status,starts_at,party_size,capacity) "
                    "VALUES (%s,%s,%s,'activity','confirmed',%s,2,4) RETURNING booking_id",
                    (world["tenant"], world[customer], "BK-" + uuid4().hex[:8], starts_at))
        return cur.fetchone()[0]


def _trip(world, days, *, customer="owner", booking=None, versions=1, linked_version=None, status="active"):
    """`days` 의 각 날짜에 항목 하나씩. `booking` 을 `linked_version` 판(기본: 최신판)의 첫 항목에 잇는다."""
    trip = uuid4()
    linked_version = versions if linked_version is None else linked_version
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO trips (trip_id,tenant_id,customer_id,title,latest_version,status) VALUES (%s,%s,%s,'시험 여행',%s,%s)",
                    (trip, world["tenant"], world[customer], versions, status))
        for version in range(1, versions + 1):
            cur.execute("INSERT INTO itinerary_versions (trip_id,version,tenant_id,reason) VALUES (%s,%s,%s,'created')",
                        (trip, version, world["tenant"]))
            for seq, day in enumerate(days, start=1):
                link = booking if (seq == 1 and version == linked_version) else None
                cur.execute("INSERT INTO itinerary_items (item_id,trip_id,version,tenant_id,seq,kind,title,starts_at,booking_id) "
                            "VALUES (%s,%s,%s,%s,%s,'activity','항목',%s,%s)",
                            (uuid4(), trip, version, world["tenant"], seq, day, link))
    return str(trip)


def _read(world, booking_id, customer="owner"):
    scope = ToolContext(tenant_id=world["tenant"], customer_id=world[customer], case_id=uuid4(), knowledge_scope=[])
    return ReadToolbox(get_connection).booking(scope, booking_id=str(booking_id))


def test_a_booking_in_the_latest_itinerary_names_that_trip(world):
    booking = _booking(world, DAY)
    trip = _trip(world, [DAY], booking=booking)
    _trip(world, [DAY])                                                        # 기간이 겹치는 다른 여행이 있어도 확인된 연결이 이긴다

    assert _read(world, booking)["trip"] == {"trip_id": trip, "matched_by": "itinerary_item", "why_unknown": None}


def test_a_link_only_in_an_old_version_is_not_a_link(world):
    booking = _booking(world, DAY)
    trip = _trip(world, [DAY], booking=booking, versions=2, linked_version=1)  # 바꾼 뒤 최신판에서는 빠졌다

    found = _read(world, booking)["trip"]
    assert found == {"trip_id": trip, "matched_by": "trip_period", "why_unknown": None}   # 남는 것은 기간 추정뿐


def test_without_a_link_the_only_trip_covering_the_day_is_a_guess(world):
    booking = _booking(world, DAY + timedelta(days=1))
    trip = _trip(world, [DAY, DAY + timedelta(days=2)])                       # 10일~12일 여행, 예약은 11일

    assert _read(world, booking)["trip"] == {"trip_id": trip, "matched_by": "trip_period", "why_unknown": None}


def test_the_day_is_the_seoul_day(world):
    booking = _booking(world, datetime(2026, 11, 11, 0, 30, tzinfo=KST))     # UTC 로는 10일 15:30
    trip = _trip(world, [datetime(2026, 11, 11, 9, 0, tzinfo=KST)])            # 서울 11일 하루짜리
    _trip(world, [datetime(2026, 11, 10, 9, 0, tzinfo=KST)])                   # 서울 10일 — UTC 날짜로 재면 이쪽이 걸린다

    assert _read(world, booking)["trip"]["trip_id"] == trip


def test_two_trips_covering_the_day_are_not_guessed(world):
    booking = _booking(world, DAY)
    _trip(world, [DAY])
    _trip(world, [DAY - timedelta(days=1), DAY + timedelta(days=1)])

    assert _read(world, booking)["trip"] == {"trip_id": None, "matched_by": None, "why_unknown": "ambiguous"}


def test_a_booking_outside_every_trip_is_not_linked(world):
    booking = _booking(world, DAY + timedelta(days=30))
    _trip(world, [DAY])
    _trip(world, [DAY + timedelta(days=30)], status="cancelled")              # 진행 중이 아닌 여행은 기간 추정에 쓰지 않는다

    assert _read(world, booking)["trip"] == {"trip_id": None, "matched_by": None, "why_unknown": "not_linked"}


def test_another_customers_trip_is_never_returned(world):
    booking = _booking(world, DAY)
    _trip(world, [DAY], customer="stranger", booking=booking)                 # 남의 여행 항목이 이 예약을 가리켜도
    _trip(world, [DAY], customer="stranger")                                   # 남의 여행 기간에 들어도

    assert _read(world, booking)["trip"] == {"trip_id": None, "matched_by": None, "why_unknown": "not_linked"}


# ── `[2026-10-15]` 맨 바깥 `trip_id` 한 칸 — 활동 → 코어 전달 3번 (TeamFlow ST4F-535) ─────────────────────────
#   활동 팀(develop 판)은 `read.booking` 결과의 `trip_id` 를 바로 읽는다. 값은 **그 예약이 든 최신 일정의 여행**(확인된 연결)이고, 없으면 `None`.
#   기간으로 추정한 여행(`trip_period`)은 `trip` 칸에만 있다 — 추정을 확정처럼 맨 바깥에 싣지 않는다.

def test_top_level_trip_id_is_the_trip_whose_latest_itinerary_holds_the_booking(world):
    booking = _booking(world, DAY)
    trip = _trip(world, [DAY], booking=booking)
    _trip(world, [DAY])                                                        # 기간이 겹치는 다른 여행

    found = _read(world, booking)
    assert found["trip_id"] == trip and found["trip"]["trip_id"] == trip


def test_top_level_trip_id_is_null_when_only_an_old_version_or_a_period_guess_points_there(world):
    booking = _booking(world, DAY)
    trip = _trip(world, [DAY], booking=booking, versions=2, linked_version=1)  # 바꾼 뒤 최신판에서는 빠졌다

    found = _read(world, booking)
    assert "trip_id" in found and found["trip_id"] is None
    assert found["trip"]["trip_id"] == trip and found["trip"]["matched_by"] == "trip_period"   # 추정은 trip 칸에만


@pytest.mark.parametrize("shape", ["ambiguous", "not_linked", "other_customers"])
def test_top_level_trip_id_is_null_when_there_is_no_trip(world, shape):
    booking = _booking(world, DAY)
    if shape == "ambiguous":
        _trip(world, [DAY])
        _trip(world, [DAY - timedelta(days=1), DAY + timedelta(days=1)])
    elif shape == "other_customers":
        _trip(world, [DAY], customer="stranger", booking=booking)

    found = _read(world, booking)
    assert found is not None and "trip_id" in found and found["trip_id"] is None


def test_top_level_trip_id_never_shows_another_customers_trip(world):
    booking = _booking(world, DAY)
    _trip(world, [DAY], customer="stranger", booking=booking)

    assert _read(world, booking, customer="owner")["trip_id"] is None
