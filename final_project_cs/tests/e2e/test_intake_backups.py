# -*- coding: utf-8 -*-
"""계획서 접수 백업 — 지우기 **전에** 통째로 담고, 관리 화면의 보관 일수가 지난 것만 지운다. `[2026-10-16 사용자 지시]`

구현: `components/intake/backup.py` · 마이그레이션 906 · 연결 `trip_delete.py` · `member_cleanup.py` · `guest_cleanup.py` · 정리 작업 `scripts/run_sweepers.py`

★지키려는 것
 ①고객이 여행을 지우면 그 여행의 접수가 원문 · 읽은 값 · 고객이 고친 값째로 백업된 **뒤에** 지워진다(이유 `trip_delete`)
 ②게스트 정리는 여행에 딸린 접수와 여행이 안 된 접수를 모두 백업한다(이유 `guest_cleanup`) — 고객 행이 지워져도 백업은 남는다
 ③백업이 실패하면 아무것도 지워지지 않는다(조용히 지우지 않는다)
 ④보관 일수는 관리 화면(`/admin/limits` 의 `retention.intake_backup_days`)에서 바꾼다 — 기본 0 은 지우지 않음, 바꾸면 이미 쌓인 백업에도 적용된다

재현:

    python -m pytest tests/e2e/test_intake_backups.py -v
"""
from __future__ import annotations

import hashlib
from uuid import UUID

import pytest
from psycopg.types.json import Json

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.intake import backup as intake_backup
from app.domains.travel_ops.components.itinerary import trip_delete
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.modules.web_account.guest_cleanup import cleanup_guests

from .test_guest_and_trip_delete import _count, _customer_of, _delete, _make_trip, _new_guest_with_trip
from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import _guest, cookies  # noqa: F401
from .test_web_guard import _client

NAME = "retention.intake_backup_days"
TEXT = "용산 가고 싶어"


@pytest.fixture(autouse=True)
def _clean_backups(api):  # noqa: F811
    yield
    web_guard.clear_cache()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM intake_backups WHERE tenant_id=%s", (api["tenant"],))
        cur.execute("DELETE FROM runtime_limits WHERE tenant_id=%s AND name=%s", (api["tenant"], NAME))


def _intake(tenant: str, customer: UUID, trip_id: UUID | None = None, text: str = TEXT) -> UUID:
    """계획서 접수 한 건 — 입력칸 글 · 규칙이 읽은 값 · 고객이 고친 값."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, status, trip_id) VALUES (%s,%s,'review',%s) RETURNING intake_id",
                    (tenant, customer, trip_id))
        intake_id = cur.fetchone()[0]
        raw = text.encode("utf-8")
        cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, sha256, size_bytes, transcript) "
                    "VALUES (%s,%s,0,'text',%s,%s,%s)", (intake_id, tenant, hashlib.sha256(raw).hexdigest(), len(raw), text))
        for method, value in (("llm_span", "용산"), ("customer", "국립중앙박물관")):
            cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, field, value_json, method, evidence) "
                        "VALUES (%s,%s,1,'items[0].title',%s,%s,%s)", (intake_id, tenant, Json(value), method, Json({"source": "text"})))
    return intake_id


def _backups(tenant: str) -> dict[UUID, tuple[str, dict]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT intake_id, reason, snapshot FROM intake_backups WHERE tenant_id=%s", (tenant,))
        return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


# ── ① 고객이 여행을 지울 때 ─────────────────────────────────────────
def test_deleting_a_trip_backs_up_its_plan_text_and_values_before_removing_them(cookies):  # noqa: F811
    _guest(cookies)
    status, trip = _make_trip(cookies)
    assert status == 201
    tenant, customer, trip_id = cookies["tenant"], _customer_of(cookies), UUID(trip["trip_id"])
    intake_id = _intake(tenant, customer, trip_id)

    assert _delete(cookies, trip_id).status_code == 200
    assert _count("SELECT count(*) FROM trip_intakes WHERE intake_id=%s", intake_id) == 0      # 원본은 지워졌다
    reason, snapshot = _backups(tenant)[intake_id]
    assert reason == "trip_delete"
    assert snapshot["intake"]["trip_id"] == str(trip_id)
    assert [s["transcript"] for s in snapshot["sources"]] == [TEXT]
    assert {(c["method"], c["value_json"]) for c in snapshot["claims"]} == {("llm_span", "용산"), ("customer", "국립중앙박물관")}


# ── ② 게스트 정리 ───────────────────────────────────────────────────
def test_guest_cleanup_backs_up_trip_and_tripless_intakes_and_the_backup_outlives_the_customer(cookies):  # noqa: F811
    tenant = cookies["tenant"]
    guest = _new_guest_with_trip(cookies, days_idle=8)                 # 기본 보존 7일을 넘긴 게스트
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT trip_id FROM trips WHERE tenant_id=%s AND customer_id=%s", (tenant, guest))
        trip_id = cur.fetchone()[0]
    with_trip, without_trip = _intake(tenant, guest, trip_id), _intake(tenant, guest, None, "내일 경복궁 10시")

    with get_connection() as conn:
        result = cleanup_guests(conn, tenant)
    assert result["customers_deleted"] == 1, result
    assert _count("SELECT count(*) FROM customers WHERE tenant_id=%s AND customer_id=%s", tenant, guest) == 0
    backups = _backups(tenant)
    assert {with_trip, without_trip} <= set(backups)
    assert {backups[with_trip][0], backups[without_trip][0]} == {"guest_cleanup"}
    assert backups[without_trip][1]["sources"][0]["transcript"] == "내일 경복궁 10시"
    assert _count("SELECT count(*) FROM intake_backups WHERE intake_id=%s AND source_customer_id=%s", without_trip, guest) == 1


# ── ③ 백업이 실패하면 ───────────────────────────────────────────────
def test_a_failed_backup_leaves_the_trip_and_the_intake_in_place(cookies, monkeypatch):  # noqa: F811
    _guest(cookies)
    status, trip = _make_trip(cookies)
    assert status == 201
    tenant, customer, trip_id = cookies["tenant"], _customer_of(cookies), UUID(trip["trip_id"])
    intake_id = _intake(tenant, customer, trip_id)

    def broken(*_args, **_kwargs):
        raise RuntimeError("백업 저장 실패")

    monkeypatch.setattr(intake_backup, "backup_trip_intakes", broken)
    with pytest.raises(RuntimeError), get_connection() as conn, conn.transaction():
        trip_delete.delete_trip(conn, tenant_id=tenant, customer_id=customer, trip_id=trip_id)
    assert _count("SELECT count(*) FROM trip_intakes WHERE intake_id=%s", intake_id) == 1
    assert _count("SELECT count(*) FROM trips WHERE trip_id=%s", trip_id) == 1
    assert intake_id not in _backups(tenant)


# ── ④ 관리 화면의 보관 일수 ─────────────────────────────────────────
def test_the_console_lists_the_backup_days_and_the_sweeper_follows_it(cookies):  # noqa: F811
    from scripts.run_sweepers import _run_web_guard

    tenant = cookies["tenant"]
    _guest(cookies)
    status, trip = _make_trip(cookies)
    assert status == 201
    customer, trip_id = _customer_of(cookies), UUID(trip["trip_id"])
    old, new = _intake(tenant, customer, trip_id), _intake(tenant, customer, trip_id, "모레 남산")
    assert _delete(cookies, trip_id).status_code == 200
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE intake_backups SET backed_up_at = now() - interval '40 days' WHERE intake_id=%s", (old,))

    client = _client()
    read, write = cookies["auth"]("limits:read"), cookies["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == NAME)
    assert (row["type"], row["value"], row["source"], row["unit"], row["min"]) == ("int", 0, "default", "일", 0)
    assert "0 이면 지우지 않습니다" in row["text_ko"]

    # 기본(0) — 40일 된 백업도 지우지 않는다
    web_guard.clear_cache()
    assert _run_web_guard(tenant)["intake_backups"] == {"skipped": "keep_forever"}
    assert {old, new} <= set(_backups(tenant))

    wrong = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "시험", "changes": {NAME: -1}})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "out_of_range"
    saved = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "백업 30일만 둔다", "changes": {NAME: 30}})
    assert saved.status_code == 200, saved.text
    assert next(r for r in saved.json()["limits"] if r["name"] == NAME)["value"] == 30

    web_guard.clear_cache()
    assert _run_web_guard(tenant)["intake_backups"] == {"deleted": 1, "days": 30}
    left = _backups(tenant)
    assert old not in left and new in left
