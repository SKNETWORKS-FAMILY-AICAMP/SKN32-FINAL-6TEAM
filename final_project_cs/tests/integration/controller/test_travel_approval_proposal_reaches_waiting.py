"""여행 승인 제안이 대조를 지나 승인 대기까지 가는가 — 실제 Team · 실제 대조 선언 · 실제 DB 예약.

★`[2026-09-17]` 이식 리포트 §6-6 「확인 필요」를 실행으로 가린다. 의심: Team 이 근거 id 로
  `tool:<팀>:<도구>` 를 드는데 Controller 대조는 **ContextPack 근거(정책)만** 센다 — 그러면
  근거가 멀쩡한 승인 제안도 「ContextPack 에 없는 근거」로 막힌다.
★여행 승인 제안을 Controller 로 지나가게 하는 시험이 이 저장소에 없었다(`tests` 에서
  `booking.cancel`·`booking.change`·`activity.change` 검색 0건).
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.case_intake import open_case
from app.application.controller import Controller
from app.core.context import PolicyChunk
from app.core.registry import TeamRegistry
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.booking_handoff import BookingHandoffTeam
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.modules.travel_ops.verification_policy import FACT_QUERIES, TRAVEL_OPS_POLICY
from app.tools.read_tools import ReadToolbox

CHUNKS = [PolicyChunk(document_id="doc_booking", chunk_no=1, content="출발 3일 전까지 취소 수수료 없음",
                      score=0.9, scope="booking")]


def _policy(*_args, **_kwargs):
    return list(CHUNKS)


class PreparingHandoff(BookingHandoffTeam):
    """취소 준비로 곧장 간다 — 이 시험은 선택이 아니라 **대조**를 본다."""

    @staticmethod
    def select_capability(intent, input_text, state=None):
        return "booking.prepare_cancel"


@pytest.fixture()
def world():
    tenant = "apprprop_" + uuid4().hex[:10]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "approval proposal"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                    (tenant, "c"))
        customer = cur.fetchone()[0]
        cur.execute("INSERT INTO bookings (tenant_id,customer_id,booking_no,kind,status,starts_at,party_size,"
                    "capacity,amount_cents) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING booking_id",
                    (tenant, customer, "BK-1", "activity", "confirmed", datetime.now(UTC) + timedelta(days=5),
                     2, 4, 5000000))
        booking = cur.fetchone()[0]
    yield tenant, customer, booking
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM bookings WHERE tenant_id=%s", (tenant,))
    cleanup_tenant(tenant)


def test_a_travel_approval_proposal_with_tool_evidence_waits_for_approval(world):
    tenant, customer, booking = world
    team = PreparingHandoff(ReadToolbox(get_connection, policy_search=_policy))
    controller = Controller(TeamRegistry([team]), policy_search=_policy, connection_factory=get_connection,
                            repository=repository, verification_policy=TRAVEL_OPS_POLICY,
                            fact_queries=FACT_QUERIES)
    with get_connection() as conn:
        opened = open_case(conn, repository=repository, tenant_id=tenant, customer_id=customer,
                           request_id="cancel-1", message="예약 취소해 주세요", channel="api", actor_type="api",
                           actor_id="test", labels={"intent": "incident_report",
                                                    "issue_code": "booking_cancel_request",
                                                    "sentiment": "neutral"})
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=opened.case_id))
    with get_connection() as conn, conn.cursor() as cur:
        case = repository.get_case(conn, tenant_id=tenant, case_id=opened.case_id)
        cur.execute("SELECT event_type, payload_json FROM case_events WHERE case_id=%s ORDER BY aggregate_version",
                    (opened.case_id,))
        events = cur.fetchall()
    assert str(case["status"]) == "waiting_approval", events[-1]
