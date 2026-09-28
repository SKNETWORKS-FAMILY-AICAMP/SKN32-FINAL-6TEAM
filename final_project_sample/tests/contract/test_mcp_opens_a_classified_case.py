"""MCP `open_support_case` 가 **분류까지** 하는가 (cs 에서 먼저 찾은 결함).

★`CLAUDE.md` §0.2 는 이 tool 을 "Case 생성·**분류 시작**까지" 로 정한다.
  그런데 2026-09-06 이전 코드는 분류를 **시도조차 하지 않고**
  `classification_unavailable` 을 적었다 — MCP 로 연 Case 는 전부 라벨 없이
  `escalated` 로 갔고 라우팅도 못 받았다(실측 확인).

★REST 접수 경로는 먼저 고쳐져 있었다. **같은 일을 하는 진입점이 둘인데 한쪽만
  고쳐진 상태**였다 — 이 패턴을 `final_project_cs` 에서 먼저 발견하고 여기도
  확인해 같이 고쳤다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from acop_basement.domain.events import EventType
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.presentation.api import cases as cases_module


@pytest.fixture()
def customer_id() -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM customers WHERE tenant_id='demo' LIMIT 1")
        row = cur.fetchone()
    if row is None:
        pytest.skip("demo 고객이 없다 — seed 를 먼저 돌린다")
    return str(row[0])


def _events(case_id: str) -> list[str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type FROM case_events WHERE case_id=%s ORDER BY created_at", (case_id,))
        return [r[0] for r in cur.fetchall()]


def test_a_case_opened_over_mcp_is_classified(monkeypatch, customer_id):
    monkeypatch.setattr(cases_module, "_mcp_classifier",
                        lambda: (lambda text: {"intent": "billing",
                                               "issue_code": "payment_failed",
                                               "sentiment": "negative"}))
    view = cases_module._mcp_open(customer_id, f"결제 문의 {uuid4().hex[:8]}", "mcp")

    assert view["intent"] == "billing"
    assert view["status"] != "escalated", "분류에 성공했는데 escalated 로 갔다"
    assert EventType.CLASSIFIED.value in _events(view["case_id"])


def test_a_broken_classifier_still_records_the_attempt(monkeypatch, customer_id):
    """★분류기를 못 만들어도 **시도한 뒤의 실패**여야 한다. 전에는 시도가 없었다."""
    monkeypatch.setattr(cases_module, "_mcp_classifier", lambda: None)
    view = cases_module._mcp_open(customer_id, f"분류 실패 확인 {uuid4().hex[:8]}", "mcp")

    assert EventType.CLASSIFICATION_FAILED.value in _events(view["case_id"])
    assert view["status"] == "escalated"


def test_repeated_identical_calls_open_one_case(monkeypatch, customer_id):
    monkeypatch.setattr(cases_module, "_mcp_classifier",
                        lambda: (lambda text: {"intent": "billing", "issue_code": "billing_other",
                                               "sentiment": "neutral"}))
    message = f"같은 문의 {uuid4().hex[:8]}"
    ids = {cases_module._mcp_open(customer_id, message, "mcp")["case_id"] for _ in range(4)}
    assert len(ids) == 1
