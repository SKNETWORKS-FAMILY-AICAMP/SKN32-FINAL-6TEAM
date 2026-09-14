"""승인 감사 기록이 승인 대기 큐에 유령 항목으로 남지 않는지 검사한다.

★결함이었던 것 (2026-08-17, 실 브라우저 승인 클릭으로 발견):
  `POST /v1/cases/{case_id}/actions/{action_id}/approve` 는 사람의 결정을
  감사 기록용으로 `action_requests` 에 `action_type="action.approve"` 행을
  하나 더 쓴다(`app/presentation/api/cases.py`). 이 행이 `status` 기본값
  (`proposed`) 그대로 저장되면, `/ui/approvals` 목록
  (`app/presentation/ui/routes.py::_actions()` — `status IN
  ('proposed','pending_approval')`)이 이미 결정 난 감사 기록을 **새로 승인이
  필요한 항목**으로 계속 보여준다. 근거가 없으니 영구히 "근거 없어 잠김"
  상태로 큐에 쌓인다 — 실제로 새로 처리할 게 없는데도 운영자에게는 계속
  막힌 대기 항목으로 보인다.

  고친 뒤: 감사 기록 행의 `status` 를 실제 결정값(`approved`/`rejected`)으로
  저장해 큐 조회에서 자동으로 빠지게 한다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.presentation.api.app import create_app
from app.presentation.security import _development_key
from app.core.settings import get_settings


@pytest.fixture()
def approval_case():
    settings = get_settings()
    tenant = settings.tenant_id
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO customers (tenant_id, external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "audit-queue-" + uuid4().hex))
            customer_id = cur.fetchone()[0]
            cur.execute("INSERT INTO bookings (tenant_id, customer_id, booking_no, kind, status, "
                        "starts_at, party_size, capacity, amount_cents) "
                        "VALUES (%s,%s,'BK-AUDITQ','activity','confirmed', "
                        "now() + interval '5 days', 1, 2, %s) RETURNING booking_id",
                        (tenant, customer_id, 3_000_000))
            booking_id = cur.fetchone()[0]
            cur.execute("INSERT INTO customer_cases (tenant_id, customer_id, status, subject, version) "
                        "VALUES (%s,%s,'waiting_approval',%s,1) RETURNING case_id",
                        (tenant, customer_id, "audit queue fixture"))
            case_id = cur.fetchone()[0]
            cur.execute("INSERT INTO case_events (tenant_id, case_id, aggregate_version, event_type, "
                        "payload_json, actor_type) VALUES (%s,%s,1,'approval_required','{}','test')",
                        (tenant, case_id))
        action_id = repository.create_action_request(
            conn, tenant_id=tenant, case_id=case_id, action_type="refund",
            arguments={"booking_id": str(booking_id), "refund_amount": 30_000},
            idempotency_key="audit-queue-" + uuid4().hex, status="pending_approval")
        conn.commit()
    yield {"tenant": tenant, "case_id": case_id, "action_id": action_id,
           "booking_id": booking_id, "customer_id": customer_id}
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM action_approvals WHERE action_id IN "
                        "(SELECT action_id FROM action_requests WHERE case_id=%s)", (case_id,))
            cur.execute("DELETE FROM action_requests WHERE case_id=%s", (case_id,))
            cur.execute("DELETE FROM case_events WHERE case_id=%s", (case_id,))
            cur.execute("DELETE FROM customer_cases WHERE case_id=%s", (case_id,))
            cur.execute("DELETE FROM supplier_bookings WHERE booking_id IN "
                        "(SELECT booking_id FROM bookings WHERE customer_id=%s)", (customer_id,))
            cur.execute("DELETE FROM bookings WHERE customer_id=%s", (customer_id,))
            cur.execute("DELETE FROM customers WHERE customer_id=%s", (customer_id,))


def _token() -> str:
    return _development_key("action:approve", get_settings().secret_key)


def _approve(client, case_id, action_id, decision):
    return client.post(f"/v1/cases/{case_id}/actions/{action_id}/approve",
                       headers={"Authorization": f"Bearer {_token()}"},
                       json={"decision": decision, "approver_id": "test-approver"})


def _pending_queue_statuses(case_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT action_type, status FROM action_requests WHERE case_id=%s "
                    "AND status IN ('proposed','pending_approval')", (case_id,))
        return cur.fetchall()


def test_approval_audit_row_does_not_appear_as_a_new_pending_item(approval_case):
    client = TestClient(create_app())
    response = _approve(client, approval_case["case_id"], approval_case["action_id"], "approved")
    assert response.status_code == 200, response.text

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM action_requests WHERE case_id=%s AND action_type='action.approve'",
                    (approval_case["case_id"],))
        row = cur.fetchone()
    assert row is not None, "감사 기록 행이 생성되지 않았다"
    assert row[0] == "approved", f"감사 기록 status 가 결정값과 다르다: {row[0]}"

    remaining = _pending_queue_statuses(approval_case["case_id"])
    ghosts = [r for r in remaining if r[0] == "action.approve"]
    assert not ghosts, f"승인 감사 기록이 대기 큐에 유령 항목으로 남았다: {ghosts}"


def test_rejection_audit_row_does_not_appear_as_a_new_pending_item(approval_case):
    client = TestClient(create_app())
    response = _approve(client, approval_case["case_id"], approval_case["action_id"], "rejected")
    assert response.status_code == 200, response.text

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM action_requests WHERE case_id=%s AND action_type='action.approve'",
                    (approval_case["case_id"],))
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "rejected", f"감사 기록 status 가 결정값과 다르다: {row[0]}"

    remaining = _pending_queue_statuses(approval_case["case_id"])
    ghosts = [r for r in remaining if r[0] == "action.approve"]
    assert not ghosts, f"거절 감사 기록이 대기 큐에 유령 항목으로 남았다: {ghosts}"
