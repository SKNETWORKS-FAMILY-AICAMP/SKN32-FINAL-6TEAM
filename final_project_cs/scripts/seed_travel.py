# -*- coding: utf-8 -*-
"""여행 도메인 데모 데이터. **재실행 안전**.

★왜 필요한가(2026-09-09). 여행 Team 여섯을 붙이고 `config/project.yaml` 등록까지
  끝냈는데, `read.booking` 이 볼 **행이 하나도 없어서** 모든 Case 가 첫 도구에서
  `unknown_예약 내역` 으로 escalate 했다. 코어(Controller·transition_case·
  outbox)는 도는데 **완주하는 갈래를 데이터가 막고 있던** 상태다.
  외부 API 가 막은 게 아니다 — `read.booking` 의 원본은 우리 DB 다.

★시각은 **실행 시각 기준 상대값**이다. 고정 날짜로 박으면 하루만 지나도
  「취소 기한 안」 시나리오가 「기한 지남」으로 바뀐다. 재실행하면 다시 맞춰진다.

★분기마다 데이터를 하나씩 둔다. 데이터로 한 번도 안 밟히는 코드 경로는
  있어도 도는지 알 수 없다(`scripts/seed.py` 의 `SKU-CST-06` 과 같은 이유).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from app.infrastructure.db.session import get_connection

DEMO = "demo"
NAMESPACE = UUID("00000000-0000-0000-0000-000000000002")


def stable(name: str) -> UUID:
    return uuid5(NAMESPACE, name)


def hours(delta: float) -> datetime:
    return datetime.now(UTC) + timedelta(hours=delta)


#: (키, 이름, 종류, 위도, 경도, 날씨민감, 확인시각오프셋h, 그시각영업, 있음, 없음)
#: ★`weather_sensitive=None` 과 좌표 `None` 을 **일부러** 하나씩 둔다 —
#:  「모름」 갈래가 데이터로 밟히지 않으면 그 코드가 도는지 알 수 없다.
#: (키, 이름, 종류, 위도, 경도, 날씨민감, 확인시각오프셋h, 그시각영업, 있음, 없음, content_id)
#: ★★마지막 칸이 **공급자 신원**이다. 카탈로그(place_catalog)에서 가져온 값이고,
#:  이게 있으면 감시가 이름으로 헤매지 않는다.
#:
#:  2026-09-10 에 이름 조회의 한계를 실측했다 —
#:    코엑스   searchKeyword2 20건 중 **정확일치 0** (공급자 제목이 다르다)
#:    개화     동명 음식점이 **2건** → 어느 쪽인지 우리가 못 고른다
#:  이름은 애매하고 바뀐다. **신원은 id 로 잡는다.**
PLACES = [
    ("palace",  "경복궁",    "activity", 37.5760, 126.9767, True,  -2, True,  [], [], "126508"),
    ("range",   "명동사격장",  "activity", 37.5619, 126.9865, False, -3, True,  [], [], "131901"),
    ("coex",    "코엑스",    "activity", 37.5117, 127.0592, False, -1, True,  [], [], "229901"),
    ("dining",  "개화",     "dining",   37.5621, 126.9818, False, -1, True,
     ["vegan"], ["halal"], "134746"),
    ("hotel",   "레드",     "lodging",  37.5584, 126.9848, None,  None, None, [], [], "2576479"),
    # ★신원을 모르는 장소를 하나 남긴다 — 「모름」 갈래가 데이터로 밟히지
    #   않으면 그 코드가 도는지 알 수 없다.
    ("nowhere", "좌표미상 체험장", "activity", None, None, True, -1, None, [], [], None),
]

#: (키, 고객, 장소키, 종류, 상태, 시작까지h, 인원, 정원, 금액, 잠김)
BOOKINGS = [
    # ① 정상 — 취소 기한(24h) 안, 옥외라 기상을 실제로 조회한다
    ("golf-ok",     "cust_01", "palace",  "activity", "confirmed",  30, 2, 4, 180_000, False),
    # ② 취소 기한 지남 — cancelable=False 갈래
    ("golf-late",   "cust_02", "range",   "activity", "confirmed",   6, 2, 4, 180_000, False),
    # ③ 인원 초과 — feasible=False 갈래
    ("palace-over", "cust_03", "coex",    "activity", "confirmed",  48, 9, 4,  12_000, False),
    # ④ 실내(날씨 무관) — 기상을 **안 부르는** 갈래
    ("palace-ok",   "cust_04", "palace",  "activity", "confirmed",  36, 2, 4,  12_000, False),
    # ⑤ 좌표 모름 — weather 가 「모름」을 돌려주는 갈래
    ("nowhere",     "cust_05", "nowhere", "activity", "confirmed",  40, 2, 8,  50_000, False),
    # ⑥ 식당 — dining.check_open / check_conditions
    ("dining-ok",   "cust_06", "dining",  "dining",   "confirmed",  20, 3, 6,       0, False),
    # ⑦ 잠긴 예약 — Lodging 은 어떤 제안도 만들지 않는다
    ("hotel",       "cust_07", "hotel",   "lodging",  "confirmed",  72, 2, 2, 240_000, True),
    # ⑧ 공급자와 **어긋난** 예약 — booking.verify 불일치 갈래
    ("golf-drift",  "cust_08", "range",   "activity", "confirmed",  60, 4, 4, 360_000, False),
]

#: (예약키, 공급자, 공급자상태) — ★⑧ 만 우리 상태와 다르다. 그게 요점이다.
SUPPLIER = [
    ("golf-ok",    "PineCreek",  "confirmed"),
    ("golf-late",  "PineCreek",  "confirmed"),
    ("golf-drift", "PineCreek",  "cancelled"),   # ★우리는 confirmed 로 알고 있다
    ("hotel",      "NamsanStay", "confirmed"),
]


def ensure_customer(conn, external_id: str) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customers (tenant_id, external_id, email_hash) VALUES (%s,%s,%s) "
            "ON CONFLICT (tenant_id, external_id) DO UPDATE SET email_hash=EXCLUDED.email_hash "
            "RETURNING customer_id",
            (DEMO, external_id, f"sha256:demo-{external_id}"))
        return cur.fetchone()[0]


def main() -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s) "
                    "ON CONFLICT (tenant_id) DO UPDATE SET name=EXCLUDED.name",
                    (DEMO, "Nimbus Travel"))

        place_ids: dict[str, UUID] = {}
        for key, name, kind, lat, lon, sensitive, confirm_h, open_slot, diet, absent, cid in PLACES:
            place_id = stable(f"place:{key}")
            place_ids[key] = place_id
            cur.execute(
                "INSERT INTO places (place_id, tenant_id, name, kind, latitude, longitude, "
                "weather_sensitive, hours_confirmed_at, open_at_slot, dietary, dietary_absent, "
                "source_name, source_content_id, source_resolved_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (place_id) DO UPDATE SET name=EXCLUDED.name, "
                "kind=EXCLUDED.kind, latitude=EXCLUDED.latitude, "
                "longitude=EXCLUDED.longitude, weather_sensitive=EXCLUDED.weather_sensitive, "
                "hours_confirmed_at=EXCLUDED.hours_confirmed_at, "
                "open_at_slot=EXCLUDED.open_at_slot, dietary=EXCLUDED.dietary, "
                "dietary_absent=EXCLUDED.dietary_absent, source_name=EXCLUDED.source_name, "
                "source_content_id=EXCLUDED.source_content_id, "
                "source_resolved_at=EXCLUDED.source_resolved_at",
                (place_id, DEMO, name, kind, lat, lon, sensitive,
                 hours(confirm_h) if confirm_h is not None else None,
                 open_slot, diet, absent,
                 'tour_api' if cid else None, cid,
                 datetime.now(UTC) if cid else None))

        booking_ids: dict[str, UUID] = {}
        for key, customer, place_key, kind, status, start_h, party, cap, amount, locked in BOOKINGS:
            booking_id = stable(f"booking:{key}")
            booking_ids[key] = booking_id
            cur.execute(
                "INSERT INTO bookings (booking_id, tenant_id, customer_id, place_id, booking_no, "
                "kind, status, starts_at, party_size, capacity, amount_cents, locked) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (booking_id) DO UPDATE SET status=EXCLUDED.status, "
                "starts_at=EXCLUDED.starts_at, party_size=EXCLUDED.party_size, "
                "capacity=EXCLUDED.capacity, amount_cents=EXCLUDED.amount_cents, "
                "locked=EXCLUDED.locked",
                (booking_id, DEMO, ensure_customer(conn, customer), place_ids[place_key],
                 f"BK-{key.upper()}", kind, status, hours(start_h), party, cap, amount, locked))

        for booking_key, supplier, status in SUPPLIER:
            cur.execute(
                "INSERT INTO supplier_bookings (supplier_booking_id, tenant_id, booking_id, "
                "supplier, supplier_ref, status, confirmed_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (supplier_booking_id) DO UPDATE SET status=EXCLUDED.status, "
                "confirmed_at=EXCLUDED.confirmed_at",
                (stable(f"supplier:{booking_key}"), DEMO, booking_ids[booking_key],
                 supplier, f"REF-{booking_key.upper()}", status, hours(-4)))

    with get_connection() as conn, conn.cursor() as cur:
        counts = {}
        for table in ("places", "bookings", "supplier_bookings"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (DEMO,))
            counts[table] = cur.fetchone()[0]
        # ★대조 대상이 실제로 어긋나 있는지 **세어서** 확인한다. 없으면
        #   `booking.verify` 의 불일치 갈래가 데이터로 안 밟힌다.
        cur.execute(
            "SELECT count(*) FROM bookings b JOIN supplier_bookings s USING (booking_id) "
            "WHERE b.tenant_id=%s AND b.status <> s.status", (DEMO,))
        counts["status_mismatch"] = cur.fetchone()[0]
    print(counts)


if __name__ == "__main__":
    main()
