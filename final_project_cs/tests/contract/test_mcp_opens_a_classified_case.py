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

import app.core.settings as settings_module
from app.domain.events import EventType
from app.infrastructure.db.session import get_connection
from app.presentation.api import cases as cases_module


@pytest.fixture()
def customer_id(monkeypatch) -> str:
    """★이 시험 전용 테넌트와 고객. 끝나면 FK 순서대로 지운다.

    ☆2026-09-14 전에는 운영 테넌트 `demo` 의 아무 고객이나(`LIMIT 1`) 골라 매 실행마다
      Case 3건을 남기고 지우지 않았다. 다른 세션이 막 만든 고객에 Case 6건이 붙어
      그 고객을 FK 때문에 지울 수 없게 됐다.

    ★`_mcp_open` 은 테넌트를 `_mcp_principal()` → 호출 시점의
      `app.core.settings.get_settings().tenant_id` 로 정한다(`cases.py`). 그래서 그
      함수를 갈아 끼우면 이 경로 전체가 전용 테넌트로 간다.
    """
    original = settings_module.get_settings()
    tenant = "test_mcp_open_" + uuid4().hex
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    customer = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)", (tenant, "mcp open test"))
        cur.execute("INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s, %s, %s)",
                    (customer, tenant, "mcp-open-customer"))
    try:
        yield str(customer)
    finally:
        # ★하나라도 FK 로 막히면 트랜잭션이 통째로 롤백돼 아무것도 안 지워진다 —
        #   `tests/integration/api/test_api_runtime.py` 의 `api_fixture` 와 같은 순서.
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM llm_calls WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
            cur.execute("DELETE FROM team_tasks WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
            cur.execute("DELETE FROM agent_runs WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)", (tenant,))
            cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def _events(case_id: str) -> list[str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type FROM case_events WHERE case_id=%s ORDER BY created_at", (case_id,))
        return [r[0] for r in cur.fetchall()]


def test_a_case_opened_over_mcp_is_classified(monkeypatch, customer_id):
    monkeypatch.setattr(cases_module, "_mcp_classifier",
                        lambda: (lambda text: {"intent": "incident_report",
                                               "issue_code": "mobility_missed_or_disrupted",
                                               "sentiment": "negative"}))
    view = cases_module._mcp_open(customer_id, f"이동 문의 {uuid4().hex[:8]}", "mcp")

    assert view["intent"] == "incident_report"
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
                        lambda: (lambda text: {"intent": "confirm_request", "issue_code": "mobility_other",
                                               "sentiment": "neutral"}))
    message = f"같은 문의 {uuid4().hex[:8]}"
    ids = {cases_module._mcp_open(customer_id, message, "mcp")["case_id"] for _ in range(4)}
    assert len(ids) == 1
