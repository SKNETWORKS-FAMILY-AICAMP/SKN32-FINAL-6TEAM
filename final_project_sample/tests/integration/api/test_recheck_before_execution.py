"""승인 직전 재검증 (v7 §9-E 두 번째 검증 · DoD-24).

★제안 생성 때 통과했어도 **사람이 승인 버튼을 누르는 사이에 사실이 바뀔 수 있다.**
  환불 가능 잔액은 그 동안에도 변한다.
  한 번만 검사하면 "승인 시점엔 맞았는데 실행 시점엔 틀린" 환불이 나간다.

여기서 재현하는 것이 정확히 그 시나리오다 —
제안을 저장한 **뒤에** 결제 금액을 낮추고 승인을 시도한다.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from acop_basement.core.idempotency import idempotency_key
from acop_basement.infrastructure.db import repository
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.presentation.api.app import create_app
from acop_basement.presentation.security import _development_key
from acop_basement.core.settings import get_settings


@pytest.fixture()
def approval_case():
    """waiting_approval 상태의 Case 와 환불 제안 하나를 만든다."""
    settings = get_settings()
    tenant = settings.tenant_id
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO customers (tenant_id, external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "recheck-" + uuid4().hex))
            customer_id = cur.fetchone()[0]
            cur.execute("INSERT INTO payments (tenant_id, customer_id, amount_cents, status, paid_at) "
                        "VALUES (%s,%s,%s,'paid',now()) RETURNING payment_id",
                        (tenant, customer_id, 3_000_000))
            payment_id = cur.fetchone()[0]
            cur.execute("INSERT INTO customer_cases (tenant_id, customer_id, status, subject, version) "
                        "VALUES (%s,%s,'waiting_approval',%s,1) RETURNING case_id",
                        (tenant, customer_id, "recheck fixture"))
            case_id = cur.fetchone()[0]
            cur.execute("INSERT INTO case_events (tenant_id, case_id, aggregate_version, event_type, "
                        "payload_json, actor_type) VALUES (%s,%s,1,'approval_required','{}','test')",
                        (tenant, case_id))
        action_id = repository.create_action_request(
            conn, tenant_id=tenant, case_id=case_id, action_type="refund",
            arguments={"payment_id": str(payment_id), "amount": 30_000},
            idempotency_key="recheck-" + uuid4().hex, status="pending_approval")
        conn.commit()
    yield {"tenant": tenant, "case_id": case_id, "action_id": action_id,
           "payment_id": payment_id, "customer_id": customer_id}
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM action_approvals WHERE action_id IN "
                        "(SELECT action_id FROM action_requests WHERE case_id=%s)", (case_id,))
            cur.execute("DELETE FROM action_requests WHERE case_id=%s", (case_id,))
            cur.execute("DELETE FROM case_events WHERE case_id=%s", (case_id,))
            cur.execute("DELETE FROM customer_cases WHERE case_id=%s", (case_id,))
            cur.execute("DELETE FROM payments WHERE customer_id=%s", (customer_id,))
            cur.execute("DELETE FROM customers WHERE customer_id=%s", (customer_id,))


def _client() -> TestClient:
    return TestClient(create_app())


def _token() -> str:
    return _development_key("action:approve", get_settings().secret_key)


def _approve(client, case_id, action_id):
    return client.post(f"/v1/cases/{case_id}/actions/{action_id}/approve",
                       headers={"Authorization": f"Bearer {_token()}"},
                       json={"decision": "approved", "approver_id": "test-approver"})


def test_approval_succeeds_when_facts_still_match(approval_case):
    """★과잉 차단이 없어야 한다. 사실이 그대로면 승인은 통과한다."""
    response = _approve(_client(), approval_case["case_id"], approval_case["action_id"])
    assert response.status_code == 200, response.text


def test_approval_is_blocked_when_the_payment_shrank_after_the_proposal(approval_case):
    """★제안 뒤에 실제 결제액이 줄면 승인이 막힌다.

    30,000원 환불 제안이 저장된 뒤 결제액을 10,000원으로 낮춘다.
    한 번만 검사했다면 3배를 환불했을 것이다.
    """
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE payments SET amount_cents=%s WHERE payment_id=%s",
                        (1_000_000, approval_case["payment_id"]))
        conn.commit()

    response = _approve(_client(), approval_case["case_id"], approval_case["action_id"])
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "verification_failed"

    # ★승인 기록이 남지 않는다 — 막혔으면 막힌 것이다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_approvals WHERE action_id=%s",
                    (approval_case["action_id"],))
        assert cur.fetchone()[0] == 0


def test_blocked_approval_records_the_reason_without_raw_values(approval_case):
    """조용히 거절하지 않는다. 그러나 금액 원문을 남기지도 않는다."""
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE payments SET amount_cents=1000 WHERE payment_id=%s",
                        (approval_case["payment_id"],))
        conn.commit()

    _approve(_client(), approval_case["case_id"], approval_case["action_id"])

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type, payload_json FROM case_events WHERE case_id=%s "
                    "ORDER BY aggregate_version DESC LIMIT 1", (approval_case["case_id"],))
        event_type, payload = cur.fetchone()
    assert event_type == "guardrail_escalated"
    assert payload["guardrail"] == "recheck_before_execution_failed"
    blob = str(payload)
    assert "30000" not in blob and "1000" not in blob.replace("recheck", "")


def test_rejection_does_not_run_the_recheck(approval_case):
    """★거절은 아무것도 실행하지 않는다. 사실이 어긋나도 거절은 되어야 한다."""
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE payments SET amount_cents=1 WHERE payment_id=%s",
                        (approval_case["payment_id"],))
        conn.commit()

    client = _client()
    response = client.post(
        f"/v1/cases/{approval_case['case_id']}/actions/{approval_case['action_id']}/approve",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"decision": "rejected", "approver_id": "test-approver"})
    assert response.status_code == 200, response.text
