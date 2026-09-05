"""MCP `open_support_case` 가 **분류까지** 하는가.

★계약이 두 곳에서 같은 말을 한다:
    `CLAUDE.md` §0.2        "Case 생성·**분류 시작**까지"
    `docs/handoff/03` §MCP  "Case **생성과 분류 시작까지**"

  그런데 2026-09-06 이전 코드는 분류를 **시도조차 하지 않고**
  `classification_unavailable` 을 적었다. 그래서 MCP 로 연 Case 는 전부
  라벨 없이 `escalated` 로 갔고 — 라우팅도 못 받았다(실측 확인).

  당시엔 이 경로에서 분류기를 구할 방법이 없어 정직하게 "못 한다" 고 적은
  것이었다. 분류 절차가 코어 1(`app/application/classification.py`)로 올라오면서
  그 이유가 없어졌다.

★분류는 생성 트랜잭션 **밖**에서 한다 — REST 접수 경로와 같은 이유다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.events import EventType
from app.infrastructure.db.session import get_connection
from app.presentation.api import cases as cases_module


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
                        lambda: (lambda text: {"intent": "shipping",
                                               "issue_code": "shipping_delayed",
                                               "sentiment": "negative"}))
    view = cases_module._mcp_open(customer_id, f"배송 문의 {uuid4().hex[:8]}", "mcp")

    assert view["intent"] == "shipping"
    assert view["status"] != "escalated", "분류에 성공했는데 escalated 로 갔다"
    assert EventType.CLASSIFIED.value in _events(view["case_id"])


def test_a_broken_classifier_still_records_the_attempt(monkeypatch, customer_id):
    """★분류기를 못 만들어도 **시도한 뒤의 실패**여야 한다. 전에는 시도가 없었다."""
    monkeypatch.setattr(cases_module, "_mcp_classifier", lambda: None)
    view = cases_module._mcp_open(customer_id, f"분류 실패 확인 {uuid4().hex[:8]}", "mcp")

    events = _events(view["case_id"])
    assert EventType.CLASSIFICATION_FAILED.value in events
    assert view["status"] == "escalated"


def test_repeated_identical_calls_open_one_case(monkeypatch, customer_id):
    """★MCP 도 동일 요청 여러 번 → Case 하나여야 한다."""
    monkeypatch.setattr(cases_module, "_mcp_classifier",
                        lambda: (lambda text: {"intent": "shipping", "issue_code": "shipping_other",
                                               "sentiment": "neutral"}))
    message = f"같은 문의 {uuid4().hex[:8]}"
    ids = {cases_module._mcp_open(customer_id, message, "mcp")["case_id"] for _ in range(4)}
    assert len(ids) == 1
