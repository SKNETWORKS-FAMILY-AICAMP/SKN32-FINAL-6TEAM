# -*- coding: utf-8 -*-
"""시험 여행 보관함 — 지우기 직전에 여행 전체를 담고, 표시를 단 여행은 감시 · 안내에서 뺀다. `[2026-10-20 사용자 결정]` D-CS-018

구현: `components/itinerary/trip_archive.py` · 마이그레이션 062 · 연결 `trip_delete.py` · `composition.wire_trip_scope`

★지키려는 것
 ①「남길 시험 여행」 표시를 단 여행을 고객이 지우면 일정 · 등록 대안 · 채팅 · 미리 준비한 대안 · 표시 내용이 보관함에 담긴 **뒤에** 지워진다
 ②시험 코드로 만든 여행은 표시 없이도 담긴다(`test_code`)
 ③실제 고객 여행(둘 다 아님)은 담지 않는다 — 지금처럼 파기(접수 원문만 접수 백업에)
 ④담기가 실패하면 아무것도 지워지지 않는다
 ⑤표시를 단 살아 있는 여행은 감시 · 안내 대상에서 빠진다(회원 여행이라도). 보관함에 담긴 여행은 감시 대상에 다시 나오지 않는다
 ⑥게스트 정리로 지워지는 시험 여행도 담긴다(이유 `guest_cleanup`)

재현:

    python -m pytest tests/e2e/test_trip_archives.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Json

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary import trip_archive, trip_delete
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.modules.web_account.guest_cleanup import cleanup_guests

from .test_guest_and_trip_delete import _count, _customer_of, _delete, _link, _make_trip, _new_guest_with_trip
from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import _guest, cookies  # noqa: F401

ALTERNATES = [{"name": "황학정", "place_id": None}, {"name": "독립관", "place_id": None}]


@pytest.fixture(autouse=True)
def _clean_archives(api):  # noqa: F811
    yield
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trip_archives WHERE tenant_id=%s", (api["tenant"],))
        cur.execute("DELETE FROM intake_backups WHERE tenant_id=%s", (api["tenant"],))


def _guest_trip(env) -> tuple[str, UUID, UUID]:
    _guest(env)
    status, trip = _make_trip(env)
    assert status == 201
    return env["tenant"], _customer_of(env), UUID(trip["trip_id"])


def _dress(tenant: str, customer: UUID, trip_id: UUID, *, test_code: bool = False) -> UUID:
    """시험 여행에 남길 것을 붙인다 — 등록 대안 · 채팅 두 줄 · 접수 한 건과 미리 준비한 대안(시험 코드 접수면 그 표시도)."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE itinerary_items i SET detail = COALESCE(i.detail, '{}'::jsonb) || jsonb_build_object('alternates', %s::jsonb) "
                    "FROM trips t WHERE t.trip_id=i.trip_id AND t.latest_version=i.version AND t.trip_id=%s AND i.seq = "
                    "(SELECT min(seq) FROM itinerary_items WHERE trip_id=t.trip_id AND version=t.latest_version)",
                    (Json(ALTERNATES), trip_id))
        assert cur.rowcount == 1
        for role, text in (("customer", "경복궁 다른 곳으로 바꿔 줘"), ("assistant", "황학정으로 바꿨어요")):
            cur.execute("INSERT INTO trip_chat_turns (tenant_id, trip_id, role, text) VALUES (%s,%s,%s,%s)", (tenant, trip_id, role, text))
        cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, status, trip_id) VALUES (%s,%s,'review',%s) RETURNING intake_id",
                    (tenant, customer, trip_id))
        intake_id = cur.fetchone()[0]
        cur.execute("INSERT INTO intake_alternatives (tenant_id, intake_id, source_id, item_index, revision, item_sig, before_sig, after_sig, body) "
                    "VALUES (%s,%s,%s,0,1,'i','b','a',%s)", (tenant, intake_id, uuid4(), Json({"candidates": ALTERNATES})))
        if test_code:
            cur.execute("INSERT INTO intake_test_scenarios (tenant_id, intake_id, customer_id, metadata) VALUES (%s,%s,%s,%s)",
                        (tenant, intake_id, customer, Json({"code": "test4"})))
    return intake_id


def _mark(tenant: str, trip_id: UUID, note: str = "x600 실서버 확인") -> None:
    with get_connection() as conn, conn.transaction():
        trip_archive.mark(conn, tenant_id=tenant, trip_id=trip_id, marked_by="live_check", note=note)


def _archive(tenant: str, trip_id: UUID) -> tuple[str, str, str | None, dict] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT kind, reason, note, snapshot FROM trip_archives WHERE tenant_id=%s AND source_trip_id=%s", (tenant, trip_id))
        return cur.fetchone()


# ── ① 표시를 단 여행 ────────────────────────────────────────────────
def test_a_marked_trip_is_copied_whole_into_the_archive_before_it_is_deleted(cookies):
    tenant, customer, trip_id = _guest_trip(cookies)
    intake_id = _dress(tenant, customer, trip_id)
    _mark(tenant, trip_id)

    assert _delete(cookies, trip_id).status_code == 200
    assert _count("SELECT count(*) FROM trips WHERE trip_id=%s", trip_id) == 0
    assert _count("SELECT count(*) FROM trip_archive_marks WHERE trip_id=%s", trip_id) == 0          # 표시는 여행과 함께 지워졌다
    kind, reason, note, snap = _archive(tenant, trip_id)
    assert (kind, reason, note) == ("marked", "trip_delete", "x600 실서버 확인")
    assert snap["trip"]["trip_id"] == str(trip_id) and snap["mark"]["marked_by"] == "live_check"
    tables = snap["tables"]
    assert [item["detail"]["alternates"] for item in tables["itinerary_items"] if (item.get("detail") or {}).get("alternates")] == [ALTERNATES]
    assert [t["text"] for t in tables["trip_chat_turns"]] == ["경복궁 다른 곳으로 바꿔 줘", "황학정으로 바꿨어요"]
    assert tables["itinerary_versions"] and snap["intake_ids"] == [str(intake_id)]
    assert [a["body"]["candidates"] for a in tables["intake_alternatives"]] == [ALTERNATES]
    assert _count("SELECT count(*) FROM intake_backups WHERE intake_id=%s", intake_id) == 1          # 접수 원문은 지금처럼 접수 백업에


# ── ② 시험 코드 여행 ────────────────────────────────────────────────
def test_a_trip_made_from_a_test_code_is_archived_without_a_mark(cookies):
    tenant, customer, trip_id = _guest_trip(cookies)
    _dress(tenant, customer, trip_id, test_code=True)

    assert _delete(cookies, trip_id).status_code == 200
    kind, reason, note, snap = _archive(tenant, trip_id)
    assert (kind, reason, note, snap["mark"]) == ("test_code", "trip_delete", None, None)


# ── ③ 실제 고객 여행 ────────────────────────────────────────────────
def test_a_real_customer_trip_is_not_archived(cookies):
    tenant, customer, trip_id = _guest_trip(cookies)
    intake_id = _dress(tenant, customer, trip_id)

    assert _delete(cookies, trip_id).status_code == 200
    assert _archive(tenant, trip_id) is None
    assert _count("SELECT count(*) FROM trip_chat_turns WHERE trip_id=%s", trip_id) == 0
    assert _count("SELECT count(*) FROM intake_backups WHERE intake_id=%s", intake_id) == 1


# ── ④ 담기 실패 ─────────────────────────────────────────────────────
def test_a_failed_archive_leaves_the_trip_in_place(cookies, monkeypatch):
    tenant, customer, trip_id = _guest_trip(cookies)
    _dress(tenant, customer, trip_id)
    _mark(tenant, trip_id)

    def broken(*_args, **_kwargs):
        raise RuntimeError("보관함 저장 실패")

    monkeypatch.setattr(trip_archive, "snapshot", broken)
    with pytest.raises(RuntimeError), get_connection() as conn, conn.transaction():
        trip_delete.delete_trip(conn, tenant_id=tenant, customer_id=customer, trip_id=trip_id)
    assert _count("SELECT count(*) FROM trips WHERE trip_id=%s", trip_id) == 1
    assert _count("SELECT count(*) FROM trip_chat_turns WHERE trip_id=%s", trip_id) == 2
    assert _archive(tenant, trip_id) is None


# ── ⑤ 감시 · 안내 ───────────────────────────────────────────────────
def test_a_marked_trip_leaves_the_watch_even_for_a_member_and_an_archived_one_never_returns(cookies):
    tenant, customer, trip_id = _guest_trip(cookies)
    _link(cookies, customer)                                       # 회원 — 게스트 제외 규칙으로는 빠지지 않는다
    store = TripStore(tenant)
    everything = datetime.now().astimezone() - timedelta(days=4000), datetime.now().astimezone() + timedelta(days=4000)
    with get_connection() as conn:
        assert trip_id in store.active_trip_ids(conn)
    _mark(tenant, trip_id)
    with get_connection() as conn:
        assert trip_id not in store.active_trip_ids(conn)
        assert all(found != trip_id for found, _ in store.due(conn, start=everything[0], end=everything[1]))
    with get_connection() as conn, conn.transaction():
        assert trip_archive.unmark(conn, tenant_id=tenant, trip_id=trip_id)
    with get_connection() as conn:
        assert trip_id in store.active_trip_ids(conn)                # 표시를 떼면 다시 감시한다
    _mark(tenant, trip_id)
    assert _delete(cookies, trip_id).status_code == 200
    with get_connection() as conn:
        assert trip_id not in store.active_trip_ids(conn)
    assert _archive(tenant, trip_id)[0] == "marked"


# ── ⑥ 게스트 정리 ───────────────────────────────────────────────────
def test_guest_cleanup_archives_a_marked_trip_before_removing_the_guest(cookies):
    tenant = cookies["tenant"]
    guest = _new_guest_with_trip(cookies, days_idle=8)                 # 기본 보존 7일을 넘긴 게스트
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT trip_id FROM trips WHERE tenant_id=%s AND customer_id=%s", (tenant, guest))
        trip_id = cur.fetchone()[0]
    _dress(tenant, guest, trip_id)
    _mark(tenant, trip_id, note="게스트 정리 시험")

    with get_connection() as conn:
        assert cleanup_guests(conn, tenant)["customers_deleted"] == 1
    kind, reason, note, snap = _archive(tenant, trip_id)
    assert (kind, reason, note) == ("marked", "guest_cleanup", "게스트 정리 시험")
    assert snap["trip"]["customer_id"] == str(guest)
