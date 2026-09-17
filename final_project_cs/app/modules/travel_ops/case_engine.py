# -*- coding: utf-8 -*-
"""Case 버전 한 벌을 조립한다 — 시나리오 모드와 하루 대조 시험이 **같은 조립**을 쓴다.

★`[결정 2026-09-17]` 시나리오용 여행 버전(`TripWatcher`·`TripDesk`)과 짝이 되는 Case 버전:

    감시     TripWatchCaseOpener  — 깨진 항목에 시스템 Case 를 연다
    고객     open_case + 분류     — 여행을 가리키는 Case(`subject_ref`)
    처리     Controller → activity·dining·mobility Team → 코어가 `itinerary.apply` 적용·통지

★점검기·경로 사건·신고 추출은 **밖에서 넣는다.** 재생(시나리오)과 실운영이 같은 조립으로
  다른 소스를 쓴다. 조립 자체는 운영과 같은 `composition` 함수를 부른다 — 따로 짠
  Controller 를 쓰면 대조가 운영을 증명하지 못한다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from app.application.case_intake import open_case
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ReadToolbox

from .itinerary import TripStore
from .subjects import KIND, make_subject_interpreter, resolve_subject
from .trip_watch_cases import TripWatchCaseOpener

ACTOR = "case_engine"


def _no_policy(*_: Any, **__: Any) -> list[Any]:
    """일정 관리 Team 은 정책 근거를 선언하지 않는다 — 불리면 안 되는 자리라 빈 값이 아니라 실패로."""
    raise RuntimeError("policy search is not wired in the itinerary case engine")


class CaseEngine:
    def __init__(self, *, tenant_id: str, check: Callable[..., dict[str, Any]], route_events: Any,
                 classifier: Callable[[str], dict[str, str]] | None,
                 report_extractor: Callable[[str], dict[str, Any] | None] | None,
                 clock: Callable[[], datetime], routes: dict[str, Any] | None = None) -> None:
        from app import composition
        from app.core.project_config import load_project_config

        self.tenant_id, self.clock, self.classifier = tenant_id, clock, classifier
        self.interpreter = make_subject_interpreter(report_extractor)
        self.store = TripStore(tenant_id)
        tools = ReadToolbox(get_connection, policy_search=_no_policy, travel=None, check=check,
                            route_events=route_events, report_extractor=report_extractor)
        config = load_project_config()
        registry = composition.build_registry(tools=tools, llm=None, config=config)
        self.controller = composition.build_controller(registry=registry, llm=None, config=config,
                                                       policy_search_fn=_no_policy)
        self.opener = TripWatchCaseOpener(store=self.store, check=check, connection_factory=get_connection,
                                          clock=clock, repository=repository, run_case=self.run,
                                          route_events=route_events, routes=routes)

    # ── 실행 ────────────────────────────────────────────────────
    def run(self, *, tenant_id: str | None = None, case_id: UUID, actor_id: str = ACTOR) -> dict[str, Any]:
        return asyncio.run(self.controller.run_case(tenant_id=tenant_id or self.tenant_id,
                                                    case_id=case_id, actor_id=actor_id))

    def tick(self):
        return self.opener.tick()

    def message(self, *, customer_id: UUID, trip_id: UUID, text: str, request_id: str,
                request: dict[str, Any] | None = None, part_id: UUID | None = None,
                base_version: int | None = None) -> dict[str, Any]:
        """고객 한 통 — 여행을 가리키는 Case 를 열고 분류한 뒤 돌린다."""
        subject: dict[str, Any] = {"kind": KIND, "id": str(trip_id),
                                   "request": {"at": self.clock().isoformat(), **(request or {})}}
        if part_id:
            subject["part_id"] = str(part_id)
        if base_version:
            subject["base_version"] = int(base_version)
        with get_connection() as conn:
            opened = open_case(conn, repository=repository, tenant_id=self.tenant_id, customer_id=customer_id,
                               request_id=request_id, message=text, channel="chat", actor_type="api",
                               actor_id=ACTOR, subject_ref=subject, subject_resolver=resolve_subject,
                               classifier=self.classifier, subject_interpreter=self.interpreter)
            status = str(repository.get_case(conn, tenant_id=self.tenant_id, case_id=opened.case_id)["status"])
        if opened.created and status == "routing":
            self.run(case_id=opened.case_id)
        return self.view(opened.case_id)

    def view(self, case_id: UUID) -> dict[str, Any]:
        with get_connection() as conn:
            case = repository.get_case(conn, tenant_id=self.tenant_id, case_id=case_id)
            with conn.cursor() as cur:
                cur.execute("SELECT event_type, payload_json FROM case_events WHERE tenant_id=%s AND case_id=%s "
                            "ORDER BY aggregate_version", (self.tenant_id, case_id))
                events = cur.fetchall()
        state = case.get("state_json") or {}
        escalation = next((payload for kind, payload in reversed(events)
                           if kind == "guardrail_escalated"), None)
        return {"case_id": str(case_id), "case_status": str(case["status"]),
                "owner_team_id": case.get("owner_team_id"),
                "classification": {"intent": case.get("intent"), "issue_code": case.get("issue_code")},
                "answer": state.get("answer"), "applied_actions": state.get("applied_actions") or [],
                "events": [kind for kind, _ in events], "escalation": escalation}


def cleanup_tenant(tenant_id: str) -> None:
    """전용 테넌트를 통째로 지운다(시나리오·시험). ★FK 순서를 지킨다."""
    runs = ("SELECT run_id FROM agent_runs WHERE case_id IN "
            "(SELECT case_id FROM customer_cases WHERE tenant_id=%s)")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        # ★세 표에는 case_id 가 없다 — 실행(run_id)·작업(action_id)을 거쳐 이어진다(001_schema.sql).
        for sql in (f"DELETE FROM team_tasks WHERE run_id IN ({runs})",
                    f"DELETE FROM llm_calls WHERE run_id IN ({runs})",
                    "DELETE FROM action_approvals WHERE action_id IN "
                    "(SELECT action_id FROM action_requests WHERE tenant_id=%s)",
                    "DELETE FROM agent_runs WHERE case_id IN "
                    "(SELECT case_id FROM customer_cases WHERE tenant_id=%s)"):
            cur.execute(sql, (tenant_id,))
        for sql in ("DELETE FROM action_requests WHERE tenant_id=%s",
                    "DELETE FROM case_events WHERE tenant_id=%s",
                    "DELETE FROM customer_cases WHERE tenant_id=%s",
                    "DELETE FROM outbox WHERE tenant_id=%s",
                    "DELETE FROM trips WHERE tenant_id=%s",
                    "DELETE FROM places WHERE tenant_id=%s",
                    "DELETE FROM customers WHERE tenant_id=%s",
                    "DELETE FROM tenants WHERE tenant_id=%s"):
            cur.execute(sql, (tenant_id,))


__all__ = ["CaseEngine", "cleanup_tenant"]
