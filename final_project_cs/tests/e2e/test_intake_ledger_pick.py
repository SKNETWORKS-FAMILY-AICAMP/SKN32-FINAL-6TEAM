# -*- coding: utf-8 -*-
"""확인 화면에서 고른 원장 식당이 원장과 이어진다. `[2026-10-10]`

결함: `wiki/records/reports/debugs/2026-10-10_고른_원장식당이_원장과_끊긴다.md`

    ① 고른 식당(`customer_pick`) — 공용 원장 식당 행과 이름이 같고 좌표가 가까운 곳이 **한 가게**일 때만 원장 가게 번호를 붙인다
    ② 확인 화면 운영시간 — 장소가 원장 가게 번호를 들고 있으면 관광공사 번호 없이도 그 가게로 판정한다
    ③ 등록 몸통 — 고른 식당의 원장 가게 번호가 장소 속성으로 넘어간다(등록 판정 · 원장 연결이 이 번호로 간다)

재현:

    python -m pytest tests/e2e/test_intake_ledger_pick.py -v

★원장(`dining.dn_place`)은 테넌트가 없는 표다 — 합성 가게(`is_synthetic`)를 세우고 끝나면 지운다.
"""
from __future__ import annotations

import json
import uuid

import pytest

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.dining import ledger as ledger_module
from app.domains.travel_ops.components.intake.assemble import _place_in
from app.domains.travel_ops.components.intake.pipeline import LEDGER_PICK_MATCH_M, _linked_ledger_pick

LAT, LON = 37.5701, 126.9894            # 종로 — 시험 가게 자리
NAME = "시험 원장 국밥집"


def _shop(cur, name: str, status: str = "active") -> str:
    uid = str(uuid.uuid4())
    cur.execute("INSERT INTO dining.dn_place (place_uid, name_ko, area, record_status, is_synthetic, lat, lng) "
                "VALUES (%s,%s,'시험',%s,true,%s,%s)", (uid, name, status, LAT, LON))
    return uid


def _public_row(cur, tenant: str, name: str, uid: str, lat: float = LAT, lon: float = LON) -> None:
    """요식 원장에서 올린 공용 식당 행 — 후보(`_ledger_places`)가 읽는 그 행."""
    cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, attributes, source_name) "
                "VALUES (%s,%s,'dining',%s,%s,%s,'dining_ledger')",
                (tenant, name, lat, lon, json.dumps({"source": "dining_ledger", "dining_place_uid": uid})))


@pytest.fixture()
def ledger(monkeypatch):
    original = settings_module.get_settings()
    tenant = "dnpick_" + uuid.uuid4().hex[:12]
    monkeypatch.setattr(settings_module, "get_settings", lambda: original.model_copy(update={"tenant_id": tenant}))
    uids: list[str] = []
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)", (tenant, "dining pick"))
    yield {"tenant": tenant, "uids": uids}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM places WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM dining.dn_place WHERE place_uid = ANY(%s::uuid[])", (uids,))
        cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def _pick(**override):
    return {"name": NAME, "kind": "dining", "latitude": LAT, "longitude": LON, "place_id": None, "content_id": None,
            "content_type_id": None, "category": None, "source": "customer_pick", "origin": "places", **override}


# ── ① 고른 식당을 원장과 잇는다 ───────────────────────────────────────
def test_a_picked_ledger_shop_gets_its_ledger_number(ledger):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        uid = _shop(cur, NAME)
        ledger["uids"].append(uid)
        _public_row(cur, ledger["tenant"], NAME, uid)
    with get_connection() as conn:
        linked = _linked_ledger_pick(conn, ledger["tenant"], _pick())
    assert linked["dining_place_uid"] == uid
    assert linked["source"] == "customer_pick"                      # 출처는 그대로 — 고객이 고른 값이다


def test_a_pick_far_from_the_ledger_row_is_not_linked(ledger):
    """같은 이름이어도 좌표가 다르면 다른 곳이다 — 잇지 않는다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        uid = _shop(cur, NAME)
        ledger["uids"].append(uid)
        _public_row(cur, ledger["tenant"], NAME, uid)
    far = LAT + (LEDGER_PICK_MATCH_M * 3) / 111_000
    with get_connection() as conn:
        linked = _linked_ledger_pick(conn, ledger["tenant"], _pick(latitude=far))
    assert "dining_place_uid" not in linked


def test_two_ledger_shops_with_the_same_name_and_place_are_not_guessed(ledger):
    """같은 자리 · 같은 이름의 가게가 둘이면 고르지 않는다 — 다른 가게의 영업시간으로 판정하는 것이 가장 나쁘다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for _ in range(2):
            uid = _shop(cur, NAME)
            ledger["uids"].append(uid)
            _public_row(cur, ledger["tenant"], NAME, uid)
    with get_connection() as conn:
        linked = _linked_ledger_pick(conn, ledger["tenant"], _pick())
    assert "dining_place_uid" not in linked


def test_an_activity_pick_is_left_alone(ledger):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        uid = _shop(cur, NAME)
        ledger["uids"].append(uid)
        _public_row(cur, ledger["tenant"], NAME, uid)
    with get_connection() as conn:
        linked = _linked_ledger_pick(conn, ledger["tenant"], _pick(kind="activity"))
    assert "dining_place_uid" not in linked


def test_a_trip_private_row_with_the_same_name_is_not_used(ledger):
    """남의 여행 전용 행(`trip_scope`)은 보지 않는다 — 공용 원장 식당 행만."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        uid = _shop(cur, NAME)
        ledger["uids"].append(uid)
        cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, attributes, source_name, trip_scope) "
                    "VALUES (%s,%s,'dining',%s,%s,%s,'dining_ledger',%s)",
                    (ledger["tenant"], NAME, LAT, LON, json.dumps({"dining_place_uid": uid}), uuid.uuid4()))
    with get_connection() as conn:
        linked = _linked_ledger_pick(conn, ledger["tenant"], _pick())
    assert "dining_place_uid" not in linked


# ── ② 확인 화면 운영시간 — 원장 가게 번호가 먼저 ─────────────────────────
def test_the_review_uses_the_ledger_number_without_a_tour_id(ledger):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        uid = _shop(cur, NAME)
        ledger["uids"].append(uid)
    with get_connection() as conn:
        assert ledger_module._catalog_uid(conn, None, {"name": "다른 이름이어도", "dining_place_uid": uid}) == uid


def test_the_review_does_not_use_a_closed_ledger_shop(ledger):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        uid = _shop(cur, NAME, status="closed")
        ledger["uids"].append(uid)
    with get_connection() as conn:
        assert ledger_module._catalog_uid(conn, None, {"name": NAME, "dining_place_uid": uid}) is None


# ── ③ 등록 몸통에 원장 가게 번호가 실린다 ──────────────────────────────
def test_the_registration_body_carries_the_ledger_number_of_a_pick():
    uid = str(uuid.uuid4())
    place = _place_in("p1", {**_pick(), "dining_place_uid": uid}, "dining")
    assert place["attributes"] == {"source": "customer_pick", "pick_origin": "places", "dining_place_uid": uid}
    plain = _place_in("p2", _pick(), "dining")
    assert "dining_place_uid" not in plain["attributes"]
