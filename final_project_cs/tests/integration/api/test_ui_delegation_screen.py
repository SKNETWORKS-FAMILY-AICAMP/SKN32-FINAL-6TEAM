# -*- coding: utf-8 -*-
"""위임 화면 — 열리는가 · 무엇이 열리는지 먼저 보여 주는가 · **실패가 보이는가**.

★이 화면이 지켜야 할 것 둘은 승인 화면에서 배운 것이다(wiki `actions/approval.md`).

    1. 실패를 조용히 삼키지 않는다   — 성공과 같은 303 을 내면 운영자는
                                        "눌렀으니 됐겠지" 로 넘어간다(2026-09-05 실제 결함)
    2. 되돌릴 수 없는 행위는 **무엇이 바뀌는지 먼저** 보여 준다

★★**200 만 보고 통과시키지 않는다.** 이 저장소에서 화면 넷이 200 을 내면서 비어 있던 적이
  있다. 그래서 여기서는 **본문에 무엇이 있는지**를 본다 — 한계 값 · 고객 id · 실패 사유.

재현:

    python -m pytest tests/integration/api/test_ui_delegation_screen.py -v
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import delegation
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.presentation import security
from app.presentation.api.app import create_app

SCREEN = "/ui/delegations"


@pytest.fixture()
def world(monkeypatch):
    original = settings_module.get_settings()
    tenant = "delegui_" + uuid4().hex[:10]
    # ★`[2026-09-22]` 화면에서 위임을 바꾸는 것은 **기본이 꺼짐**이다(`/ui/*` 에 로그인이 없다).
    #   이 시험들은 그 기능을 보는 것이라 켜고 돌린다 — 기본이 막힌다는 것은 아래 따로 본다.
    patched = original.model_copy(update={"tenant_id": tenant, "ui_delegation_write_enabled": True})
    monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
    monkeypatch.setattr(security, "get_settings", lambda: patched)

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "delegation ui"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') "
                    "RETURNING customer_id", (tenant,))
        customer = cur.fetchone()[0]

    yield TestClient(create_app(), raise_server_exceptions=False), tenant, customer
    cleanup_tenant(tenant)


def test_the_screen_opens_and_says_what_is_being_entrusted(world):
    """★빈 화면이 아니다 — 맡기는 범위가 실제로 적혀 있어야 한다."""
    client, _tenant, _customer = world
    response = client.get(SCREEN)
    assert response.status_code == 200
    body = response.text
    scope = delegation.Scope.from_guardrails()
    assert "지금 맡기는 범위" in body
    assert f"{scope.max_per_action_cents // 100:,}원" in body      # 건당 상한
    assert f"{scope.max_changes_per_booking}회" in body            # 횟수 상한
    # 위임이 없으면 없다고 적는다 — 0 을 지어내지 않는다
    assert "위임 기록이 없습니다" in body


def test_the_menu_can_reach_it(world):
    client, _tenant, _customer = world
    assert SCREEN in client.get("/ui/cases").text


def test_granting_shows_what_changes_before_it_changes_anything(world):
    """★되돌릴 수 없는 쪽은 확인 단계를 둔다. **그 단계에서는 아직 아무것도 안 바뀐다.**"""
    client, tenant, customer = world
    response = client.post(SCREEN, data={"action": "grant", "customer_id": str(customer),
                                         "actor_id": "op-1", "note": "고객이 맡김"},
                           follow_redirects=False)
    assert response.status_code == 200
    body = response.text
    assert "확인 — 맡긴다" in body
    assert str(customer) in body
    assert "이 범위가 열립니다" in body

    # ★아직 열리지 않았다 — 확인 화면은 읽기만 한다
    with get_connection() as conn:
        assert delegation.state(conn, tenant_id=tenant,
                                customer_id=customer)["state"] == delegation.STATE_ABSENT


def test_confirming_actually_grants_and_the_row_appears(world):
    client, tenant, customer = world
    response = client.post(SCREEN, data={"action": "grant", "confirm": "yes",
                                         "customer_id": str(customer),
                                         "actor_id": "op-1", "note": "고객이 맡김"},
                           follow_redirects=False)
    assert response.status_code == 303
    with get_connection() as conn:
        assert delegation.state(conn, tenant_id=tenant,
                                customer_id=customer)["state"] == delegation.STATE_LIVE

    body = client.get(SCREEN).text
    assert str(customer) in body and "살아 있음" in body and "op-1" in body


def test_revoking_from_the_screen_closes_it(world):
    client, tenant, customer = world
    with get_connection() as conn, conn.transaction():
        delegation.grant(conn, tenant_id=tenant, customer_id=customer, by="op-1", note="맡김")

    response = client.post(SCREEN, data={"action": "revoke", "customer_id": str(customer),
                                         "actor_id": "op-2", "note": "고객이 거둠"},
                           follow_redirects=False)
    assert response.status_code == 303, response.text
    with get_connection() as conn:
        assert delegation.state(conn, tenant_id=tenant,
                                customer_id=customer)["state"] == delegation.STATE_REVOKED


# ─────────────────────────────────────────────────────────────────────────────
# 실패가 보이는가 — 승인 화면의 교훈
# ─────────────────────────────────────────────────────────────────────────────

def test_revoking_nothing_shows_the_reason_instead_of_a_silent_redirect(world):
    """★조용한 303 이면 운영자는 거둔 줄 안다 — 실제로는 아무 일도 없었는데."""
    client, _tenant, customer = world
    response = client.post(SCREEN, data={"action": "revoke", "customer_id": str(customer),
                                         "actor_id": "op", "note": "n"}, follow_redirects=False)
    assert response.status_code != 303, "거두지 못했는데 성공과 같은 리다이렉트로 삼켜졌다"
    assert response.status_code == 200
    body = response.text
    assert "거두지 못했습니다" in body
    assert "no_live_delegation" in body
    assert SCREEN in body           # 돌아갈 길은 남긴다


def test_an_unknown_customer_shows_the_reason(world):
    client, _tenant, _customer = world
    response = client.post(SCREEN, data={"action": "grant", "customer_id": str(uuid4()),
                                         "actor_id": "op", "note": "n"}, follow_redirects=False)
    assert response.status_code == 200
    assert "이 고객을 확인하지 못했습니다" in response.text
    assert "404" in response.text


def test_a_malformed_customer_id_is_told_plainly(world):
    """★서버까지 보내 422 를 받아 오면 무엇이 잘못됐는지가 오히려 흐려진다."""
    client, _tenant, _customer = world
    response = client.post(SCREEN, data={"action": "grant", "customer_id": "cust_01",
                                         "actor_id": "op", "note": "n"}, follow_redirects=False)
    assert response.status_code == 200
    assert "고객 id 형식이 아닙니다" in response.text
    assert "cust_01" in response.text


def test_by_default_the_screen_cannot_change_a_delegation(monkeypatch):
    """★`/ui/*` 에는 로그인이 없다 — **서 있는 권한**을 주는 버튼을 기본으로 열어 두지 않는다.

    2026-08-18 에 같은 이유로 Composer 화면을 이 앱에서 지웠다(D-CS-001). 위임은 한 건 승인이
    아니라 그 고객의 다음 자동 실행 전부를 여는 것이라 기준이 더 세다.
    """
    original = settings_module.get_settings()
    tenant = "delegoff_" + uuid4().hex[:10]
    patched = original.model_copy(update={"tenant_id": tenant})      # 기본값(꺼짐) 그대로
    monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
    monkeypatch.setattr(security, "get_settings", lambda: patched)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "delegation off"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') RETURNING customer_id",
                    (tenant,))
        customer = cur.fetchone()[0]
    try:
        client = TestClient(create_app(), raise_server_exceptions=False)
        response = client.post(SCREEN, data={"action": "grant", "customer_id": str(customer),
                                             "actor_id": "ops-1", "note": "확인"})
        assert response.status_code == 200 and "이 화면에서는 위임을 바꿀 수 없습니다" in response.text
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM delegations WHERE tenant_id=%s", (tenant,))
            assert cur.fetchone()[0] == 0, "막혔다면서 위임이 생겼다"
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            for table in ("delegation_events", "delegations", "customers", "tenants"):
                cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))
