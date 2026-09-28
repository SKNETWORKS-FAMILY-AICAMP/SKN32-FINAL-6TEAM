# -*- coding: utf-8 -*-
"""위임을 **주고 거두는 경로** — v11 §12 DoD-18·19 · wiki `teams/booking-handoff.md`.

★**왜 이 파일이 생겼나.** 위임 범위 판정(`delegation.py`)과 `delegations` 표(019)는
  2026-09-22 에 만들었는데 **주고 거두는 자리가 없었다** — 운영자가 손으로 SQL 을 쳐야 했다.
  「위임은 언제든 철회할 수 있다」가 제품의 약속인데 누를 자리가 없으면 그건 말뿐이다.

★여기서 재는 것은 넷이다.

    1. 권한         scope 없이는 못 부른다 · 읽기 키로는 못 바꾼다
    2. 주기         행과 **이력**이 남는다(누가·언제·왜)
    3. 거두기       거둔 **뒤 자동 실행이 실제로 막히는가** ← 이것이 핵심이다
    4. 삼키지 않기  거둘 것이 없으면 「거뒀다」고 답하지 않는다(409)

★3 은 판정기(`delegation.judge`)를 **실제 예약 행**에 대고 직접 부른다. 판정이 「범위 안」을
  내주던 예약이 철회 뒤에는 `delegation_revoked` 로 막히는지 본다 — API 가 돌려준 말이
  아니라 **게이트의 판정**을 본다.

★이력은 **다시 주기 뒤에도 남는지**를 따로 잰다. `delegations` 한 행은 덮어써지므로
  (`ON CONFLICT DO UPDATE`), 021 의 append-only 표가 없으면 철회 기록이 사라진다.

재현:

    python -m pytest tests/integration/api/test_delegation_api.py -v
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import delegation
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.presentation import security
from app.presentation.api.app import create_app
from scripts.measure_delegation_scope import new_booking

READ = "delegation:read"
WRITE = "delegation:write"


def _key(scope: str) -> dict[str, str]:
    token = security._development_key(scope, settings_module.get_settings().secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def world(monkeypatch):
    """깨끗한 테넌트 · 고객 하나 · **범위 안** 예약 하나."""
    original = settings_module.get_settings()
    tenant = "delegapi_" + uuid4().hex[:10]
    patched = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
    monkeypatch.setattr(security, "get_settings", lambda: patched)

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "delegation api"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') "
                    "RETURNING customer_id", (tenant,))
        customer = cur.fetchone()[0]
    with get_connection() as conn, conn.transaction():
        booking = new_booking(conn, tenant=tenant, customer=customer, no="TGT")

    client = TestClient(create_app(), raise_server_exceptions=False)
    yield client, tenant, customer, booking

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM supplier_bookings WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM bookings WHERE tenant_id=%s", (tenant,))
    cleanup_tenant(tenant)


def _judge(tenant: str, customer: UUID, booking: str) -> delegation.Decision:
    """게이트에게 직접 묻는다 — 지금 이 예약의 자동 실행이 열리나."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT booking_id, kind, starts_at, amount_cents FROM bookings "
                    "WHERE tenant_id=%s AND booking_id=%s", (tenant, booking))
        row = dict(zip(("booking_id", "kind", "starts_at", "amount_cents"), cur.fetchone()))
    with get_connection() as conn:
        return delegation.judge(conn, tenant_id=tenant, customer_id=customer, booking=row)


# ─────────────────────────────────────────────────────────────────────────────
# 1. 권한
# ─────────────────────────────────────────────────────────────────────────────

def test_without_a_token_nothing_is_readable_or_changeable(world):
    client, _tenant, customer, _booking = world
    assert client.get("/v1/delegations").status_code == 401
    assert client.post(f"/v1/delegations/{customer}/grant",
                       json={"actor_id": "op", "note": "n"}).status_code == 401


def test_a_read_key_cannot_grant_or_revoke(world):
    """★읽기와 쓰기를 나눈 이유가 여기서 보인다 — 현황을 보는 사람이 문을 열지 못한다."""
    client, _tenant, customer, _booking = world
    body = {"actor_id": "op", "note": "n"}
    assert client.post(f"/v1/delegations/{customer}/grant", json=body,
                       headers=_key(READ)).status_code == 403
    assert client.post(f"/v1/delegations/{customer}/revoke", json=body,
                       headers=_key(READ)).status_code == 403


def test_an_approval_key_is_not_enough(world):
    """★승인 권한이 위임 권한을 겸하지 않는다. 승인은 한 건, 위임은 서 있는 권한이다."""
    client, _tenant, customer, _booking = world
    response = client.post(f"/v1/delegations/{customer}/grant",
                           json={"actor_id": "op", "note": "n"}, headers=_key("action:approve"))
    assert response.status_code == 403


def test_another_tenants_customer_is_not_even_acknowledged(world):
    client, _tenant, _customer, _booking = world
    assert client.get(f"/v1/delegations/{uuid4()}", headers=_key(READ)).status_code == 404


def test_who_and_why_are_required(world):
    """★근거 없이 위임 상태를 바꾸지 않는다 — 공백만 보내도 거부한다."""
    client, _tenant, customer, _booking = world
    for body in ({"actor_id": "", "note": "n"}, {"actor_id": "op", "note": ""}):
        response = client.post(f"/v1/delegations/{customer}/grant", json=body, headers=_key(WRITE))
        assert response.status_code == 422, body


# ─────────────────────────────────────────────────────────────────────────────
# 2. 주기
# ─────────────────────────────────────────────────────────────────────────────

def test_granting_opens_the_gate_and_records_who_when_why(world):
    client, tenant, customer, booking = world
    assert _judge(tenant, customer, booking).limit == delegation.LIMIT_DELEGATION_ABSENT

    response = client.post(f"/v1/delegations/{customer}/grant",
                           json={"actor_id": "op-1", "note": "고객이 전화로 맡김"},
                           headers=_key(WRITE))
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "live"

    # ★게이트에게 직접 묻는다 — API 가 한 말이 아니라 판정을 본다
    assert _judge(tenant, customer, booking).allowed is True

    detail = client.get(f"/v1/delegations/{customer}", headers=_key(READ)).json()
    assert detail["granted_by"] == "op-1"
    assert [e["action"] for e in detail["history"]] == ["granted"]
    assert detail["history"][0]["note"] == "고객이 전화로 맡김"


def test_the_listing_carries_the_limits_it_opens(world):
    """★무엇을 여는지 모르는 채로 누르게 하지 않는다 — 목록과 같은 응답에 범위가 온다."""
    client, _tenant, customer, _booking = world
    client.post(f"/v1/delegations/{customer}/grant", json={"actor_id": "op", "note": "n"},
                headers=_key(WRITE))
    data = client.get("/v1/delegations", headers=_key(READ)).json()
    assert data["counts"] == {"live": 1, "revoked": 0, "total": 1}
    keys = {row["key"] for row in data["limits"]}
    assert {"max_per_action_cents", "max_total_cents", "kinds",
            "max_changes_per_booking"} <= keys
    # ★한계 값은 설정에서 온다 — 화면이 숫자를 지어내지 않는지 본다
    scope = delegation.Scope.from_guardrails()
    per_action = next(r for r in data["limits"] if r["key"] == "max_per_action_cents")
    assert f"{scope.max_per_action_cents // 100:,}원" == per_action["value"]


def test_the_listing_never_carries_another_customer_identifier(world):
    """★링크·화면에 내부 식별자를 늘리지 않는다(PII)."""
    client, _tenant, customer, _booking = world
    client.post(f"/v1/delegations/{customer}/grant", json={"actor_id": "op", "note": "n"},
                headers=_key(WRITE))
    row = client.get("/v1/delegations", headers=_key(READ)).json()["rows"][0]
    assert "external_id" not in row and "email_hash" not in row


# ─────────────────────────────────────────────────────────────────────────────
# 3. 거두기 — 자동 실행이 실제로 막히는가 (DoD-19)
# ─────────────────────────────────────────────────────────────────────────────

def test_revoking_closes_the_gate(world):
    client, tenant, customer, booking = world
    client.post(f"/v1/delegations/{customer}/grant", json={"actor_id": "op", "note": "맡김"},
                headers=_key(WRITE))
    assert _judge(tenant, customer, booking).allowed is True

    response = client.post(f"/v1/delegations/{customer}/revoke",
                           json={"actor_id": "op-2", "note": "고객이 거둠"}, headers=_key(WRITE))
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "revoked"

    decision = _judge(tenant, customer, booking)
    assert decision.allowed is False
    assert decision.limit == delegation.LIMIT_DELEGATION_REVOKED
    assert "op-2" in decision.observed


def test_revoking_twice_does_not_claim_success(world):
    """★거둘 것이 없는데 200 을 내면 운영자는 "눌렀으니 됐겠지" 로 넘어간다."""
    client, _tenant, customer, _booking = world
    body = {"actor_id": "op", "note": "n"}
    client.post(f"/v1/delegations/{customer}/grant", json=body, headers=_key(WRITE))
    client.post(f"/v1/delegations/{customer}/revoke", json=body, headers=_key(WRITE))

    again = client.post(f"/v1/delegations/{customer}/revoke", json=body, headers=_key(WRITE))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "no_live_delegation"


def test_revoking_something_never_granted_is_also_not_a_success(world):
    client, _tenant, customer, _booking = world
    response = client.post(f"/v1/delegations/{customer}/revoke",
                           json={"actor_id": "op", "note": "n"}, headers=_key(WRITE))
    assert response.status_code == 409
    assert response.json()["error"]["state"] == "absent"


# ─────────────────────────────────────────────────────────────────────────────
# 4. 이력이 덮이지 않는다 (마이그레이션 021)
# ─────────────────────────────────────────────────────────────────────────────

def test_regranting_does_not_erase_who_revoked_it(world):
    """★★019 만으로는 이 기록이 사라진다 — 다시 주기가 `revoked_by` 를 NULL 로 덮는다.

    「그때는 위임 안에 있었다」를 나중에 확인하려면 행위가 쌓여야 한다.
    """
    client, _tenant, customer, _booking = world
    client.post(f"/v1/delegations/{customer}/grant",
                json={"actor_id": "op-1", "note": "처음 맡김"}, headers=_key(WRITE))
    client.post(f"/v1/delegations/{customer}/revoke",
                json={"actor_id": "op-2", "note": "잠시 거둠"}, headers=_key(WRITE))
    again = client.post(f"/v1/delegations/{customer}/grant",
                        json={"actor_id": "op-3", "note": "다시 맡김"}, headers=_key(WRITE))
    assert again.json()["regranted"] is True

    detail = client.get(f"/v1/delegations/{customer}", headers=_key(READ)).json()
    # 지금 상태는 덮인다(그게 `delegations` 의 일이다)
    assert detail["state"] == "live" and detail["revoked_by"] is None
    # ★이력은 안 덮인다
    assert [e["action"] for e in detail["history"]] == ["granted", "revoked", "granted"]
    assert [e["actor_id"] for e in detail["history"]] == ["op-3", "op-2", "op-1"]
