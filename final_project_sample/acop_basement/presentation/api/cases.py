from __future__ import annotations

import asyncio
import hashlib
import inspect
from typing import Any, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from acop_basement.application.controller import ControllerError
from acop_basement.core.contracts import InvalidTransition, StateConflict
from acop_basement.core.idempotency import idempotency_key
from acop_basement.core.transition import transition_case
from acop_basement.domain.events import EventType
from acop_basement.infrastructure.db import repository
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.application.proposal_guard import audit_payload, describe, recheck_before_execution
from acop_basement.presentation.security import Principal, masked, require_scope

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
    # ★버그사냥 2026-08-17 (라운드 04·06·08) — 이 필드가 없었다. 서버는 message
    #   원문을 해시해 "resume_token_hash" 라고 이름만 붙였을 뿐, 실제 발급된
    #   토큰(24h TTL·일회성, CaseService.new_resume_token())과는 전혀 대조하지
    #   않았다 — case:write scope 만 있으면 진짜 토큰 없이도 대기 Case 를
    #   재개시킬 수 있었다. 이제 진짜 토큰을 받아 Controller.resume() 으로
    #   검증한다(docs/handoff/03 §1-4).
    token: str = Field(min_length=1)


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
                # ★버그사냥 2026-08-18 (라운드 08) — try 가 classifier() 뿐 아니라
                #   뒤이은 CLASSIFIED transition_case() 호출까지 감싸고 있었다.
                #   그 결과 전이 자체의 버그(StateConflict/InvalidTransition)도
                #   전부 "classification_failed" 로 뭉개졌다 — 상태 충돌을 분류
                #   실패로 보고하면 원인을 못 찾는다(CLAUDE.md §3). classifier
                #   호출만 감싼다 — CLASSIFIED 전이 자체의 실패는 있는 그대로
                #   드러낸다(test_create_does_not_relabel_a_transition_bug_as_classification_failure).
                try:
                    result = classifier(masked(request.message)) if classifier else None
                    if not result or not all(k in result for k in ("intent", "issue_code", "sentiment")):
                        raise ValueError("classifier unavailable")
                except Exception:
                    result = None
                if result is not None:
                    transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1, event_type=EventType.CLASSIFIED,
                                    payload=result, actor_type="api", actor_id=principal.key_id)
                else:
                    transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1, event_type=EventType.CLASSIFICATION_FAILED,
                                    payload={"failure_code": "classification_failed"}, actor_type="api", actor_id=principal.key_id)
                repository.create_action_request(conn, tenant_id=tenant, case_id=case_id, action_type="case.create",
                                                arguments={"request_id": request.request_id}, idempotency_key=idem)
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
        # ★버그사냥 2026-08-17 (라운드 04·06·08) — 예전엔 이 핸들러가 직접
        #   VALID_INPUT 을 발행했다. message 원문을 해시해 "resume_token_hash"
        #   라고 이름만 붙였을 뿐 실제 발급 토큰과 대조하지 않았다 — 진짜 검증
        #   로직(CaseService.validate_resume(): hash·만료·일회성)은
        #   Controller.resume() 안에만 있었는데 이 REST 경로가 그걸 안 거쳤다.
        #   이제 Controller.resume() 을 그대로 거친다 — 그 메서드가 검증부터
        #   재실행까지 전부 끝낸다(내부에서 run_case() 를 부른다. 여기서 또
        #   부르면 이미 resolved 된 Case 에 완료 이벤트를 두 번 적용하려다
        #   InvalidTransition 이 난다 — 실제로 테스트에서 재현해 확인했다).
        if controller is None:
            raise _error(500, "misconfigured", "controller not configured for resume")
        with get_connection() as conn:
            _case_or_404(conn, principal, case_id)
        try:
            outcome = controller.resume(tenant_id=principal.tenant_id, case_id=case_id, token=request.token,
                                        actor_id=principal.key_id, event_id=request.request_id)
            if inspect.isawaitable(outcome):
                outcome = asyncio.run(outcome)
        except ControllerError as exc:
            raise _error(401, "invalid_resume_token", str(exc)) from exc
        except StateConflict as exc: raise _error(409, "state_conflict", "state conflict") from exc
        except InvalidTransition as exc: raise _error(422, "invalid_transition", "invalid state transition") from exc
        with get_connection() as conn:
            return _view(repository.get_case(conn, tenant_id=principal.tenant_id, case_id=case_id))

    @router.post("/v1/cases/{case_id}/actions/{action_id}/approve")
    def approve(case_id: UUID, action_id: UUID, request: ApprovalRequest, principal: Principal = Depends(require_scope("action:approve"))):
        if request.decision not in {"approved", "rejected"}: raise _error(400, "contract_violation", "invalid decision")
        with get_connection() as conn:
            case = _case_or_404(conn, principal, case_id)
            idem = idempotency_key(tenant_id=principal.tenant_id, request_id=request.approver_id, action_type="action.approve", business_subject=f"{action_id}:{request.decision}")

            # ★버그사냥 2026-08-17 (라운드 01, 처리는 라운드 08) — v7 §9-E 는
            #   재검증을 두 번 하라고 한다(제안 생성 때 + 실행 직전). 재검증과
            #   실제 승인 커밋 사이에 창이 있어, 그 사이 다른 요청이 참조된
            #   payment/subscription 을 바꿔도 못 잡을 수 있다는 게 원래 finding
            #   이었다.
            #
            #   ★시도했다가 되돌린 것 — 재검증과 승인 write 를 하나의
            #   `with conn.transaction():` 로 합치고 그 **안에서** `conn.commit()`
            #   을 부르려 했다. psycopg3 는 이걸 명시적으로 금지한다
            #   ("Explicit commit() forbidden within a Transaction context" —
            #   직접 재현해 확인). 그래서 실패 경로(escalate)는 원래처럼 **자기
            #   만의 트랜잭션**을 쓰고, 그 블록이 정상 종료(=커밋)된 뒤에
            #   raise 한다 — 이 커넥션은 그 앞의 `_case_or_404()` 조회 때문에
            #   이미 ambient 트랜잭션이 열려 있어, `with conn.transaction():`
            #   가 진짜 최상위 커밋이 아니라 savepoint 로 동작한다. 그래서
            #   escalate 뒤에도 명시적 `conn.commit()` 이 필요하다(이것도
            #   직접 재현해 확인 — 없으면 예외 전파 시 escalate 기록이 롤백된다).
            #
            #   ★그래도 좁힌 것 — 재검증을 승인 write 직전, **같은 함수 호출
            #   시퀀스 안에서 곧바로** 한다(사람이 승인 버튼을 누른 뒤 이
            #   핸들러가 도는 동안은 원래도 사람이 기다리는 구간이 아니다).
            #   완전한 원자성(다른 트랜잭션이 끼어들 수 없음을 보장)은 참조
            #   행에 대한 row lock 이 있어야 하는데, 그건 이 수정의 범위 밖이다
            #   — 별도로 다룰 항목으로 남긴다(아래 리포트 참조).
            with conn.cursor() as cur:
                cur.execute("SELECT action_id FROM action_requests WHERE action_id=%s AND tenant_id=%s AND case_id=%s", (action_id, principal.tenant_id, case_id))
                if cur.fetchone() is None: raise _error(404, "not_found", "resource not found")
                cur.execute("SELECT action_id FROM action_requests WHERE tenant_id=%s AND idempotency_key=%s", (principal.tenant_id, idem))
                if cur.fetchone() is not None:
                    return _view(case)

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

                    repository.create_action_request(conn, tenant_id=principal.tenant_id, case_id=case_id, action_type="action.approve",
                                                    arguments={"action_id": str(action_id), "decision": request.decision}, idempotency_key=idem)
                    repository.create_approval(conn, action_id=action_id, decision=request.decision, approver_id=request.approver_id)
                    transition_case(conn, tenant_id=principal.tenant_id, case_id=case_id, expected_version=case["version"], event_type=EventType.APPROVED if request.decision == "approved" else EventType.REJECTED,
                                    payload={"action_id": str(action_id), "approver_id": request.approver_id}, actor_type="human", actor_id=request.approver_id)
            return _view(repository.get_case(conn, tenant_id=principal.tenant_id, case_id=case_id))
    return router


def _mcp_principal() -> Principal:
    from acop_basement.core.settings import get_settings
    from acop_basement.core.settings import get_guardrails
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
    # ★버그사냥 2026-08-17 — request_id 를 계산만 하고 안 썼다. REST POST /v1/cases
    #   (67-92행)와 달리 idempotency 조회·기록이 없어 같은 MCP 재시도가 매번
    #   새 Case 를 만들었다(DoD-11 이 "동일 요청 10회 → 1행"을 증명한다고 주장한
    #   대상은 REST 경로뿐이었다). REST 와 같은 조회-후-생성 패턴을 그대로 쓴다.
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
