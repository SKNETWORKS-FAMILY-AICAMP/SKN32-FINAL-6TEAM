"""Case 생성 감사 기록이 승인 대기 큐에 유령 항목으로 남지 않는지 검사한다.

★결함이었던 것 (2026-08-17, `action.approve` 유령 항목 결함과 같은 뿌리):
  `POST /v1/cases` 는 idempotency 대조용으로 `action_requests` 에
  `action_type="case.create"` 행을 하나 더 쓴다(`app/presentation/api/cases.py`).
  이 행이 `status` 기본값(`proposed`) 그대로 저장되면, `/ui/approvals` 목록
  (`_actions()` — `status IN ('proposed','pending_approval')`)이 **Case 를 만들
  때마다** 근거 없는 유령 항목을 하나씩 쌓는다 — 이미 끝난 일(Case 생성)인데
  승인이 필요한 새 제안처럼 보인다.

  고친 뒤: 이 행을 처음부터 종결 상태(`succeeded`)로 저장해 큐 조회에서 빠지게 한다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.api.app import create_app


@pytest.fixture()
def case_create_fixture(monkeypatch):
    original = settings_module.get_settings()
    tenant = "test_case_create_" + uuid4().hex
    customer = uuid4()
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)

    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)", (tenant, "case create audit test"))
            cur.execute("INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s, %s, %s)", (customer, tenant, "customer-1"))

    def token() -> str:
        return "Bearer " + security._development_key("case:write", original.secret_key)

    classifier = lambda _message: {"intent": "order", "issue_code": "order_other", "sentiment": "neutral"}
    yield {"client": TestClient(create_app(classifier=classifier)), "tenant": tenant, "customer": customer, "token": token}

    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)", (tenant,))
            cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def test_new_case_does_not_leave_a_ghost_item_in_the_approval_queue(case_create_fixture):
    response = case_create_fixture["client"].post(
        "/v1/cases",
        headers={"Authorization": case_create_fixture["token"]()},
        json={"request_id": "ghost-check", "customer_id": str(case_create_fixture["customer"]),
              "message": "환불 문의드립니다", "channel": "test"},
    )
    assert response.status_code == 201, response.text

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM action_requests WHERE tenant_id=%s AND action_type='case.create'",
                    (case_create_fixture["tenant"],))
        row = cur.fetchone()
    assert row is not None, "case.create 감사 기록 행이 생성되지 않았다"
    assert row[0] != "proposed", f"case.create 감사 기록이 기본 status(proposed) 로 남아 대기 큐에 유령 항목이 된다: {row[0]}"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT action_type, status FROM action_requests WHERE tenant_id=%s "
                    "AND status IN ('proposed','pending_approval')", (case_create_fixture["tenant"],))
        pending = cur.fetchall()
    ghosts = [r for r in pending if r[0] == "case.create"]
    assert not ghosts, f"Case 생성이 대기 큐에 유령 항목을 남겼다: {ghosts}"
