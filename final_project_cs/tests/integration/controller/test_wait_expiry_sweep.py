"""대기 만료 되잡기를 실제 DB 전이로 확인한다 — 고객이 돌아오지 않아도 `waiting_input` 이 `escalated` 로 간다(INV-CS-RT-018).

`test_conversation_resume.py` 의 여행 재개 시험 Case(자기 tenant)를 그대로 쓴다.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.controller import ControllerError
from app.application.wait_expiry_sweeper import sweep_expired_waits
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from tests.integration.controller.test_conversation_resume import resume, saved, travel  # noqa: F401  (fixture)


def _expire(tenant, case_id, seconds_ago=1):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE customer_cases SET state_json=jsonb_set(state_json,'{resume_token_expires_at}',to_jsonb(%s::text)) "
                        "WHERE tenant_id=%s AND case_id=%s",
                        ((datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat(), tenant, case_id))
        conn.commit()


def _outbox(tenant):
    with get_connection() as conn:
        return conn.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s", (tenant,)).fetchone()[0]


def test_abandoned_expired_wait_is_escalated_without_customer_notice(travel):  # noqa: F811
    _, team, tenant, _, case_id, first = travel
    _expire(tenant, case_id)
    before = _outbox(tenant)
    with get_connection() as conn:
        counts = sweep_expired_waits(conn, tenant_id=tenant, actor_id="wait_expiry_sweeper", limit=10)
    assert counts["expired"] == 1 and counts["errored"] == 0
    case = saved(tenant, case_id)
    assert case["status"] == "escalated" and case["version"] == first["version"] + 1
    with get_connection() as conn:
        last = repository.get_case_events(conn, tenant_id=tenant, case_id=case_id)[-1]
    assert last["event_type"] == "wait_expired" and last["actor_type"] == "system"
    assert last["actor_id"] == "wait_expiry_sweeper" and last["payload_json"] == {"wait_reason": "customer_input"}
    assert _outbox(tenant) == before                                  # 고객 알림 없음
    # 늦게 온 답장은 만료로 끝나고 Case 를 되살리지 않는다(자동 resolve 없음)
    with pytest.raises(ControllerError):
        resume(travel)
    assert saved(tenant, case_id)["status"] == "escalated" and len(team.tasks) == 1
    with get_connection() as conn:                                     # 다음 회차는 다시 집지 않는다
        assert sweep_expired_waits(conn, tenant_id=tenant, actor_id="wait_expiry_sweeper", limit=10)["scanned"] == 0


def test_live_wait_and_other_tenants_are_untouched(travel):  # noqa: F811
    _, _, tenant, _, case_id, first = travel
    with get_connection() as conn:
        counts = sweep_expired_waits(conn, tenant_id=tenant, actor_id="wait_expiry_sweeper", limit=10)
    assert counts["scanned"] == 1 and counts["waiting"] == 1 and counts["expired"] == 0
    _expire(tenant, case_id)
    with get_connection() as conn:
        other = sweep_expired_waits(conn, tenant_id=tenant + "_other", actor_id="wait_expiry_sweeper", limit=10)
    assert other["scanned"] == 0
    assert saved(tenant, case_id)["status"] == "waiting_input"
    assert saved(tenant, case_id)["version"] == first["version"]
