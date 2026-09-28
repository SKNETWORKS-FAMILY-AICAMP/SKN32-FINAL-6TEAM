# -*- coding: utf-8 -*-
"""업체 예약 **변경 링크** — v11 §12 DoD-16·17.

    16  업체 건은 실행하지 않고 **변경 링크**를 만든다
    17  변경 링크에 **바뀔 항목 · 대안 · 차액**이 들어 있다

★계획서 v11 §4-C 의 통지 예시가 이 화면이다 — "같은 날 15:20 편이 있고 차액은 +42,000원입니다.
  … 항공권 변경은 아래 링크에서 진행해 주세요."

★**차액을 지어내지 않는지**를 따로 잰다(결정 15 · 근거 없는 문장 금지). 가격을 모르는 상태를
  일부러 만들어, 화면이 0원이나 추정치가 아니라 「확인되지 않았습니다」와 **이유**를 적는지 본다.

★**원장이 안 바뀌는지**도 여기서 잰다. 링크는 「우리가 안 바꾼다」의 대안이므로, 링크가 나가는
  경로가 공급자 원장을 건드리면 링크가 있어도 DoD-16 은 거짓이다. 등급을 `real` 로 두고 잰다.

재현:

    python -m pytest tests/e2e/test_booking_change_link.py -v
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.booking_actions import BookingChange
from app.modules.travel_ops.itinerary import Item, TripStore
from app.modules.travel_ops.plan_link import plan_token
from app.modules.travel_ops.trip_api import build_trip_router, change_token
from app.presentation import security
from app.presentation.api.app import create_app

START = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)

#: 1인 가격(원)만 다른 세 장소. ★`없음` 은 `price_krw` 칸 자체가 없다 — 「모름」을 만드는 자리다.
PLACES = {"본래": 31_000, "대안A": 35_000, "대안B": 62_000, "가격없음": None}


def _insert_place(cur, tenant: str, name: str, price: int | None) -> UUID:
    attributes = {"district": "중구", "indoor": True}
    if price is not None:
        attributes["price_krw"] = price
    cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
                "attributes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING place_id",
                (tenant, name, "activity", 37.56, 126.98, False,
                 json.dumps(attributes, ensure_ascii=False)))
    return cur.fetchone()[0]


@pytest.fixture()
def world(monkeypatch):
    """예약 한 건 + 그 예약에 걸린 일정 항목 + 항목이 들고 있는 「다른 안」 둘."""
    original = settings_module.get_settings()
    tenant = "chglink_" + uuid4().hex[:12]
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "change link"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                    (tenant, "c"))
        customer = cur.fetchone()[0]
        places = {name: _insert_place(cur, tenant, name, price) for name, price in PLACES.items()}
        # ★예약 금액은 **원의 100배**다(`verification_policy.py` 의 scale=100) — 31,000원 × 2명.
        cur.execute("INSERT INTO bookings (tenant_id,customer_id,place_id,booking_no,kind,status,"
                    "starts_at,party_size,capacity,amount_cents) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING booking_id",
                    (tenant, customer, places["본래"], "BK-AIR-1", "activity", "confirmed",
                     START, 2, 4, 62_000 * 100))
        booking = cur.fetchone()[0]
        # ★등급을 **적어서** 실제 공급자로 둔다(기본값도 `real` 이지만 시험 의도를 드러낸다).
        cur.execute("INSERT INTO supplier_bookings (tenant_id,booking_id,supplier,supplier_ref,"
                    "status,tier) VALUES (%s,%s,%s,%s,%s,%s)",
                    (tenant, booking, "seoul-air", "SUP-AIR-1", "confirmed", "real"))

    store = TripStore(tenant)
    alternates = [
        {"key": str(places["대안A"]), "name": "대안A", "place_id": str(places["대안A"]),
         "option": None, "option_label": "같은 날 15:20", "walk_min": 4,
         "starts_at": (START + timedelta(minutes=20)).isoformat(),
         "ends_at": (START + timedelta(minutes=110)).isoformat()},
        {"key": str(places["대안B"]), "name": "대안B", "place_id": str(places["대안B"]),
         "option": None, "option_label": None, "walk_min": 9,
         "starts_at": (START + timedelta(hours=2)).isoformat(), "ends_at": None},
    ]
    with get_connection() as conn, conn.transaction():
        trip_id, _ = store.create_trip(
            conn, customer_id=customer, title="서울 하루", locale="ko", party_size=2,
            items=[Item(item_id=uuid4(), seq=1, kind="activity", title="스카이데크 전망",
                        place_id=places["본래"], starts_at=START,
                        ends_at=START + timedelta(minutes=90), booking_id=booking,
                        detail={"alternates": alternates})])

    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other",
                                                          "sentiment": "neutral"},
                                   domain_routers=[build_trip_router()]))
    link = f"/booking-change/{booking}?t={change_token(tenant, booking)}"
    yield {"client": client, "tenant": tenant, "customer": customer, "booking": booking,
           "trip_id": trip_id, "places": places, "link": link}

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for sql in ("DELETE FROM outbox WHERE tenant_id=%s",
                    "DELETE FROM itinerary_items WHERE tenant_id=%s",
                    "DELETE FROM itinerary_versions WHERE tenant_id=%s",
                    "DELETE FROM trips WHERE tenant_id=%s",
                    "DELETE FROM supplier_bookings WHERE tenant_id=%s",
                    "DELETE FROM bookings WHERE tenant_id=%s",
                    "DELETE FROM places WHERE tenant_id=%s",
                    "DELETE FROM customers WHERE tenant_id=%s",
                    "DELETE FROM tenants WHERE tenant_id=%s"):
            cur.execute(sql, (tenant,))


def _ledger(booking) -> tuple[str, str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, tier FROM supplier_bookings WHERE booking_id=%s", (booking,))
        return cur.fetchone()


def _booking_status(booking) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM bookings WHERE booking_id=%s", (booking,))
        return cur.fetchone()[0]


# invariant: DoD-17
def test_the_link_shows_the_item_the_alternatives_and_the_difference(world):
    """★세 값이 **다** 있어야 통과다 — 바뀔 항목 · 대안 · 차액."""
    page = world["client"].get(world["link"])
    assert page.status_code == 200, page.text
    text = page.text

    assert "바뀔 항목" in text and "BK-AIR-1" in text and "본래" in text
    assert "2026-10-03" in text                       # 현재 시각
    assert "seoul-air" in text and "SUP-AIR-1" in text
    assert "스카이데크 전망" in text                    # 이 예약에 걸린 일정 항목

    assert "대안" in text and "같은 날 15:20" in text and "대안B" in text

    # 차액 = (대안 1인 가격 − 본래 1인 가격) × 인원 2명. 35,000−31,000=4,000 → +8,000원
    assert "차액 +8,000원" in text and "인원 2명" in text
    assert "차액 +62,000원" in text                    # (62,000−31,000)×2 — v11 §4-C 예시와 같은 자리
    # ★아는 값을 모른다고 적지 않는다 — 「모름」 표시(`class="unknown"`)가 한 군데도 없다
    assert "확인되지 않았습니다" not in text and 'class="unknown"' not in text

    view = world["client"].get(world["link"] + "&format=json").json()
    assert view["booking_no"] == "BK-AIR-1" and view["paid_krw"] == 62_000
    assert view["alternatives_source"] == "item_booking_id" and view["heads"] == 2
    assert [a["difference_krw"] for a in view["alternatives"]] == [8_000, 62_000]
    assert all(a["difference_unknown"] is None for a in view["alternatives"])
    assert "customer_id" not in view                   # ★링크를 받은 사람에게 내부 id 를 보이지 않는다


# invariant: DoD-16
def test_a_wrong_token_never_says_whether_the_booking_exists(world):
    """★계획서 링크와 같은 규칙 — 틀리면 **있는지도 말하지 않는다**(404)."""
    booking, tenant = world["booking"], world["tenant"]
    assert world["client"].get(f"/booking-change/{booking}?t={'0' * 32}").status_code == 404
    # ★계획서 토큰으로 예약 화면이 열리지 않는다 — 같은 비밀 키라 접두를 갈라 두었다
    assert world["client"].get(
        f"/booking-change/{booking}?t={plan_token(tenant, booking)}").status_code == 404
    # ★남의 예약 토큰으로도 못 연다
    assert world["client"].get(
        f"/booking-change/{uuid4()}?t={change_token(tenant, booking)}").status_code == 404


# invariant: DoD-17
def test_a_difference_we_cannot_compute_says_so_instead_of_inventing_one(world):
    """★★**차액을 지어내지 않는다**(v11 결정 15 · 근거 없는 문장 금지).

    가격 칸이 없는 장소를 「다른 안」에 넣고, 화면이 0원·추정치가 아니라
    「확인되지 않았습니다」와 **어느 쪽을 몰라서인지**를 적는지 본다.
    """
    store = TripStore(world["tenant"])
    unpriced = world["places"]["가격없음"]
    with get_connection() as conn, conn.transaction():
        trip, items = store.latest(conn, world["trip_id"])
        item = items[0]
        item.detail = {"alternates": [{"key": str(unpriced), "name": "가격없음",
                                       "place_id": str(unpriced), "option": None,
                                       "option_label": None, "walk_min": 3,
                                       "starts_at": None, "ends_at": None}]}
        store.append_version(conn, trip_id=world["trip_id"], base_version=trip["version"],
                             items=[item], reason="customer_request", causes=[])

    view = world["client"].get(world["link"] + "&format=json").json()
    alternative = view["alternatives"][0]
    assert alternative["price_krw"] is None
    assert alternative["difference_krw"] is None                     # ★0 이 아니다
    assert alternative["difference_unknown"] == "대안의 1인 가격이 확인되지 않았습니다"

    text = world["client"].get(world["link"]).text
    assert "차액 <span class=\"unknown\">확인되지 않았습니다</span>" in text
    assert "대안의 1인 가격이 확인되지 않았습니다" in text
    assert "차액 +" not in text and "차액 없음" not in text           # ★수를 만들어 넣지 않았다

    # 반대쪽도 모름으로 만들면 이유가 바뀐다 — 어느 쪽을 몰라서인지 구분해 적는다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE places SET attributes = attributes - 'price_krw' WHERE place_id=%s",
                    (world["places"]["본래"],))
    alternative = world["client"].get(world["link"] + "&format=json").json()["alternatives"][0]
    assert alternative["difference_unknown"] == \
        "지금 예약한 곳과 대안 모두 1인 가격이 확인되지 않았습니다"


# invariant: DoD-16
def test_a_real_supplier_booking_is_handed_off_by_link_and_the_ledger_stays_put(world):
    """★**실행하지 않고** 링크를 만든다 — 실제 공급자 원장이 한 글자도 안 바뀐다.

    `booking.change` 적용기를 그대로 부른다(코어가 승인 뒤 부르는 것과 같은 호출). 등급은
    `real` 이다 — 등급 게이트에 걸리기 전에 **애초에 원장을 건드리는 SQL 이 없다**는 것이
    이 경로의 성질이고, 그래서 업체 건이 실행되지 않는다.
    """
    before = _ledger(world["booking"])
    case_id = uuid4()
    with get_connection() as conn, conn.transaction():
        applied = BookingChange().apply(conn, tenant_id=world["tenant"],
                                        customer_id=world["customer"], case_id=case_id,
                                        arguments={"booking_id": str(world["booking"]),
                                                   "reason": "업체가 결항을 통보했다"})

    assert _ledger(world["booking"]) == before == ("confirmed", "real")   # ★원장 그대로
    assert _booking_status(world["booking"]) == "change_requested"        # 우리 쪽만 바뀐다

    # 인계 기록(바깥함)에 링크가 실려 있고, 그 링크가 실제로 열린다
    assert len(applied.outbox) == 1
    payload = applied.outbox[0].payload
    assert payload["booking_no"] == "BK-AIR-1" and payload["reason"] == "업체가 결항을 통보했다"
    assert applied.summary["change_url"] == payload["change_url"]
    path = "/" + payload["change_url"].split("://", 1)[1].split("/", 1)[1]
    page = world["client"].get(path)
    assert page.status_code == 200 and "BK-AIR-1" in page.text and "차액 +8,000원" in page.text
    assert "업체에서 직접 변경해 주세요" in page.text
