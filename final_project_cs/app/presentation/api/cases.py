from __future__ import annotations

import asyncio
import hashlib
import inspect
from typing import Any, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.contracts import InvalidTransition, StateConflict
from app.application.controller import ControllerError
from app.core.idempotency import idempotency_key
from app.core.transition import transition_case
from app.domain.events import EventType
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.application.proposal_guard import audit_payload, describe, recheck_before_execution
from app.presentation.security import Principal, masked, require_scope

Classifier = Callable[[str], dict[str, str]]


class CreateCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    idempotency_key: str | None = None
    tenant_id: str | None = None
    customer_id: UUID
    message: str = Field(min_length=1)
    channel: str


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    message: str = Field(min_length=1)
    token: str = Field(min_length=1)
    expected_version: int | None = None


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    approver_id: str
    note: str | None = None


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message}})


def _case_or_404(conn, principal: Principal, case_id: UUID, customer_id: UUID | None = None):
    case = repository.get_case(conn, tenant_id=principal.tenant_id, case_id=case_id)
    if case is None or (customer_id is not None and case["customer_id"] != customer_id):
        raise _error(404, "not_found", "resource not found")
    return case


def _view(case: dict[str, Any]) -> dict[str, Any]:
    return {"case_id": str(case["case_id"]), "status": str(case["status"]), "version": case["version"],
            "intent": case.get("intent"), "issue_code": case.get("issue_code"), "sentiment": case.get("sentiment"),
            "links": {"self": f"/v1/cases/{case['case_id']}"}}


def build_router(classifier: Classifier | None = None, controller: Any | None = None) -> APIRouter:
    router = APIRouter()
    @router.post("/v1/cases", status_code=201)
    def create(request: CreateCase, principal: Principal = Depends(require_scope("case:write"))):
        tenant = principal.tenant_id
        idem = idempotency_key(tenant_id=tenant, request_id=request.request_id, action_type="case.create", business_subject=f"{request.customer_id}:{request.message}")
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT case_id FROM action_requests WHERE tenant_id=%s AND idempotency_key=%s", (tenant, idem))
                    existing = cur.fetchone()
                if existing:
                    case = repository.get_case(conn, tenant_id=tenant, case_id=existing[0])
                    return _view(case)
                case_id = repository.create_case(conn, tenant_id=tenant, customer_id=request.customer_id, subject=request.message, state_json={"request_id": request.request_id})
                transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0, event_type=EventType.CREATED,
                                payload={"channel": request.channel, "message": request.message}, actor_type="api", actor_id=principal.key_id)
                try:
                    result = classifier(masked(request.message)) if classifier else None
                    if not result or not all(k in result for k in ("intent", "issue_code", "sentiment")):
                        raise ValueError("classifier unavailable")
                    transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1, event_type=EventType.CLASSIFIED,
                                    payload=result, actor_type="api", actor_id=principal.key_id)
                except Exception:
                    transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1, event_type=EventType.CLASSIFICATION_FAILED,
                                    payload={"failure_code": "classification_failed"}, actor_type="api", actor_id=principal.key_id)
                # ★status 를 기본값(proposed)으로 두면 이 idempotency 감사 기록 행이
                #   `/ui/approvals` 대기 큐(status IN proposed,pending_approval)에
                #   Case 를 만들 때마다 근거 없는 유령 항목으로 쌓인다 — action.approve
                #   행과 같은 결함(2026-08-17 발견, docs/reports/debugs/
                #   2026-08-17_2250_UI승인큐_유령항목.md). Case 생성 자체는 승인 대상이
                #   아니라 이미 끝난 일이므로 종결 상태로 남긴다.
                repository.create_action_request(conn, tenant_id=tenant, case_id=case_id, action_type="case.create",
                                                arguments={"request_id": request.request_id}, idempotency_key=idem,
                                                status="succeeded")
            view = _view(repository.get_case(conn, tenant_id=tenant, case_id=case_id))
        if controller is not None and view["status"] == "routing":
            outcome = controller.run_case(tenant_id=tenant, case_id=case_id, actor_id=principal.key_id)
            if inspect.isawaitable(outcome):
                outcome = asyncio.run(outcome)
            if isinstance(outcome, dict):
                view.update({key: value for key, value in outcome.items() if key in {"status", "version", "run_id", "next_action", "resume_token"}})
        return view

    @router.get("/v1/cases")
    def list_cases(customer_id: UUID = Query(...), limit: int = Query(20, ge=1, le=100), principal: Principal = Depends(require_scope("case:read"))):
        with get_connection() as conn:
            rows = repository.list_cases(conn, tenant_id=principal.tenant_id, customer_id=customer_id, limit=limit)
        return [{k: (str(v) if isinstance(v, UUID) else v) for k, v in row.items()} for row in rows]

    @router.get("/v1/cases/{case_id}")
    def detail(case_id: UUID, customer_id: UUID | None = Query(None), principal: Principal = Depends(require_scope("case:read"))):
        with get_connection() as conn:
            case = _case_or_404(conn, principal, case_id, customer_id)
            events = repository.get_case_events(conn, tenant_id=principal.tenant_id, case_id=case_id)
        return {**_view(case), "answer": case["state_json"].get("answer"), "pending_actions": [],
                "evidence": [{"source_type": "case_event", "source_id": str(e["event_id"]), "claim": e["event_type"], "value": {}, "observed_at": e["created_at"]} for e in events]}

    @router.post("/v1/cases/{case_id}/messages")
    def message(case_id: UUID, request: MessageRequest, principal: Principal = Depends(require_scope("case:write"))):
        if controller is None:
            raise _error(500, "misconfigured", "controller not configured for resume")
        with get_connection() as conn:
            case = _case_or_404(conn, principal, case_id)
        try:
            outcome = controller.resume(tenant_id=principal.tenant_id, case_id=case_id, token=request.token,
                                        actor_id=principal.key_id, event_id=request.request_id)
            if inspect.isawaitable(outcome):
                outcome = asyncio.run(outcome)
        except ControllerError as exc:
            raise _error(401, "invalid_resume_token", str(exc)) from exc
        except StateConflict as exc:
            raise _error(409, "state_conflict", "state conflict") from exc
        except InvalidTransition as exc:
            raise _error(422, "invalid_transition", "invalid state transition") from exc
        with get_connection() as conn:
            return _view(repository.get_case(conn, tenant_id=principal.tenant_id, case_id=case_id))

    @router.post("/v1/cases/{case_id}/actions/{action_id}/approve")
    def approve(case_id: UUID, action_id: UUID, request: ApprovalRequest, principal: Principal = Depends(require_scope("action:approve"))):
        if request.decision not in {"approved", "rejected"}: raise _error(400, "contract_violation", "invalid decision")
        with get_connection() as conn:
            case = _case_or_404(conn, principal, case_id)
            idem = idempotency_key(tenant_id=principal.tenant_id, request_id=request.approver_id, action_type="action.approve", business_subject=f"{action_id}:{request.decision}")

            # ★v7 §9-E — 검증은 두 번이다. 여기가 두 번째, **실행 직전 재검증**이다.
            #   제안 생성 때 맞았어도 사람이 승인 버튼을 누르는 사이에
            #   잔액·구독 상태가 바뀔 수 있다.
            #
            # ★승인 트랜잭션 **밖**에서 한다. 안에서 하고 409 를 던졌더니
            #   방금 쓴 escalated 이벤트가 예외와 함께 **롤백돼 사라졌다** —
            #   "조용히 무시하지 않는다" 가 그대로 깨졌다. 거부 기록은 남아야 한다.
            # ★존재 확인이 먼저다. 없는 action 에 재검증을 돌리면
            #   404 여야 할 요청이 엉뚱한 상태 전이를 시도한다
            #   (routing 상태 Case 에 escalated 를 쓰려다 상태기계에 걸렸다).
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM action_requests WHERE action_id=%s AND tenant_id=%s AND case_id=%s",
                            (action_id, principal.tenant_id, case_id))
                if cur.fetchone() is None:
                    raise _error(404, "not_found", "resource not found")

            # ★재검증으로 escalated 를 쓸 수 있는 상태는 waiting_approval 뿐이다.
            #   다른 상태의 승인 요청은 아래 전이에서 상태기계가 판단한다.
            if request.decision == "approved" and case["status"] == "waiting_approval":
                # ★대조 어휘는 도메인 선언에서 가져온다. 이 파일은 무엇을 대조하는지 모른다.
                from app.composition import build_verification
                policy, queries = build_verification()
                mismatches = recheck_before_execution(
                    conn, tenant_id=principal.tenant_id, case=case, action_id=action_id,
                    policy=policy, queries=queries) if queries else []
                if mismatches:
                    with conn.transaction():
                        transition_case(conn, tenant_id=principal.tenant_id, case_id=case_id,
                                        expected_version=case["version"],
                                        event_type=EventType.GUARDRAIL_ESCALATED,
                                        payload={"guardrail": "recheck_before_execution_failed",
                                                 "observed": [describe(mismatches)],
                                                 "state_patch": {"rejected_proposal_audit": audit_payload(
                                                     action_type="action.approve", mismatches=mismatches,
                                                     case_id=case_id)}},
                                        actor_type="human", actor_id=request.approver_id)
                    conn.commit()
                    raise _error(409, "verification_failed",
                                 "승인 시점의 사실과 제안이 어긋납니다: " + describe(mismatches))

            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT action_id FROM action_requests WHERE action_id=%s AND tenant_id=%s AND case_id=%s", (action_id, principal.tenant_id, case_id))
                    if cur.fetchone() is None: raise _error(404, "not_found", "resource not found")
                    cur.execute("SELECT action_id FROM action_requests WHERE tenant_id=%s AND idempotency_key=%s", (principal.tenant_id, idem))
                    if cur.fetchone() is not None:
                        return _view(case)

                    # ★status 를 기본값(proposed)으로 두면 이 감사 기록 행이
                    #   `/ui/approvals` 의 "대기 중" 목록(status IN proposed,pending_approval)에
                    #   근거 없는 유령 항목으로 영구히 남는다 — 2026-08-17 실 브라우저 승인
                    #   클릭으로 발견. 이미 내려진 결정(approved/rejected)이므로 그 값을 그대로 status 로 쓴다.
                    repository.create_action_request(conn, tenant_id=principal.tenant_id, case_id=case_id, action_type="action.approve",
                                                    arguments={"action_id": str(action_id), "decision": request.decision}, idempotency_key=idem,
                                                    status=request.decision)
                    repository.create_approval(conn, action_id=action_id, decision=request.decision, approver_id=request.approver_id)
                    transition_case(conn, tenant_id=principal.tenant_id, case_id=case_id, expected_version=case["version"], event_type=EventType.APPROVED if request.decision == "approved" else EventType.REJECTED,
                                    payload={"action_id": str(action_id), "approver_id": request.approver_id}, actor_type="human", actor_id=request.approver_id)
            return _view(repository.get_case(conn, tenant_id=principal.tenant_id, case_id=case_id))
    return router


def _mcp_principal() -> Principal:
    """Resolve the MCP caller, refusing when the module is declared off.

    ★tool 세 개가 전부 이 함수를 지난다. 그래서 `mcp` 모듈의 게이트를 여기 둔다.
      2026-08-30 이전에는 게이트가 아예 없어서, 선언에서 모듈을 꺼도 개인 AI 의
      read-only 접근이 그대로 살아 있었다(`docs/handoff/08` §2 가 끄면 사라져야
      한다고 지정한 표면이다).
    """
    from app.core.project_config import load_project_config
    from app.core.settings import get_settings
    from app.core.settings import get_guardrails
    load_project_config().require_module("mcp", "MCP tool surface")
    if "mcp:read" not in set(get_guardrails().get("security.mcp_allowed_scopes")):
        raise RuntimeError("mcp:read is not configured")
    return Principal(get_settings().tenant_id, frozenset({"mcp:read"}), "mcp")


def _mcp_cases(customer_id: str, limit: int) -> list[dict]:
    principal = _mcp_principal()
    with get_connection() as conn:
        rows = repository.list_cases(conn, tenant_id=principal.tenant_id, customer_id=UUID(customer_id), limit=min(limit, 100))
    return [{k: (str(v) if isinstance(v, UUID) else v) for k, v in row.items()} for row in rows]


def _mcp_detail(customer_id: str, case_id: str) -> dict:
    principal = _mcp_principal()
    with get_connection() as conn:
        case = _case_or_404(conn, principal, UUID(case_id), UUID(customer_id))
    return _view(case)


def _mcp_open(customer_id: str, message: str, channel: str) -> dict:
    principal = _mcp_principal()
    request = CreateCase(request_id=hashlib.sha256(f"mcp:{customer_id}:{message}".encode()).hexdigest(), customer_id=UUID(customer_id), message=message, channel=channel)
    tenant = principal.tenant_id
    idem = idempotency_key(tenant_id=tenant, request_id=request.request_id, action_type="mcp.open_support_case", business_subject=f"{request.customer_id}:{request.message}")
    # Reuse the REST creation path's state machine without exposing write actions.
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT case_id FROM action_requests WHERE tenant_id=%s AND idempotency_key=%s", (tenant, idem))
                existing = cur.fetchone()
            if existing:
                return _view(repository.get_case(conn, tenant_id=tenant, case_id=existing[0]))
            safe_message = masked(message)
            case_id = repository.create_case(conn, tenant_id=tenant, customer_id=request.customer_id, subject=safe_message)
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0, event_type=EventType.CREATED, payload={"channel": channel, "message": safe_message}, actor_type="mcp", actor_id=principal.key_id)
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1, event_type=EventType.CLASSIFICATION_FAILED, payload={"failure_code": "classification_unavailable"}, actor_type="mcp", actor_id=principal.key_id)
            repository.create_action_request(conn, tenant_id=tenant, case_id=case_id, action_type="mcp.open_support_case",
                                            arguments={"request_id": request.request_id}, idempotency_key=idem)
        return _view(repository.get_case(conn, tenant_id=tenant, case_id=case_id))
