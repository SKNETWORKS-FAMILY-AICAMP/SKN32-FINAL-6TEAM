"""Case execution loop: route, build context, execute a Team, then transition."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import UUID, uuid4

from app.core.context import ContextBroker, ContextInputs
from app.core.contracts import CaseStatus, InvalidTransition, NextAction, TeamTask, TeamResult, RESUME_NODE_FOR_WAIT, StateConflict
from app.core.idempotency import idempotency_key, request_id_for_case
from app.core.registry import TeamRegistry, RegistryError
from app.core.settings import get_guardrails
from app.core.transition import OutboxMessage, transition_case
from app.domain.events import EventType
from app.core.verification import Mismatch
from app.application.case_service import ActiveRunError, CaseService, ResumeTokenError
from app.application.proposal_guard import audit_payload, check_proposal, describe


class ControllerError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, registry: TeamRegistry, *, context_broker: ContextBroker | None = None,
                 policy_search: Callable[..., list[Any]] | None = None,
                 connection_factory: Callable | None = None, repository: Any | None = None,
                 case_service: CaseService | None = None, graph_revision: str = "controller-v1",
                 team_executor: Any | None = None, broker: Any | None = None,
                 verification_policy: Any | None = None, fact_queries: Any = (),
                 response_review: Any | None = None) -> None:
        # ★대조 어휘는 주입받는다. Controller 는 어떤 필드를 대조하는지 모른다 —
        #   알면 basement 가 특정 업무 도메인에 묶인다.
        from app.core.verification import VerificationPolicy
        self.verification_policy = verification_policy or VerificationPolicy()
        self.fact_queries = tuple(fact_queries or ())
        # The composition root supplies all concrete adapters.  These lazy
        # defaults retain backwards compatibility for focused application
        # tests that construct Controller directly.
        if repository is None:
            from app.infrastructure.db import repository as default_repository
            repository = default_repository
        if connection_factory is None:
            from app.infrastructure.db.session import get_connection
            connection_factory = get_connection
        if policy_search is None:
            from app.infrastructure.rag.retriever import search_policy
            policy_search = search_policy
        if team_executor is None:
            from app.core.remote_team.executor import LocalTeamExecutor
            team_executor = LocalTeamExecutor(registry)
        self.registry = registry
        self.context_broker = context_broker or ContextBroker()
        self.policy_search = policy_search
        self.connection_factory = connection_factory
        self.repository = repository
        self.case_service = case_service or CaseService(graph_revision=graph_revision)
        self.team_executor = team_executor
        self.broker = broker
        self.response_review = response_review

    def _capability(self, case: dict[str, Any]) -> str:
        """Return the capability selected by the injected Team registry."""
        intent = case.get("intent")
        entry = self.registry.resolve(case_type=intent or "", intent=intent)
        return self.registry.capability_for(entry, intent)

    def _policy(self, tenant_id: str, query: str, scopes: list[str]) -> tuple[list[Any], bool]:
        try:
            return self.policy_search(tenant_id, query, scopes), False
        except Exception:
            # Retrieval failure is an explicit signal to ContextBroker, not an empty result.
            return [], True

    def _task(self, case: dict[str, Any], entry, run_id: UUID, *, resume: bool = False,
              resume_node: str | None = None, retrieval_failed: bool = False) -> TeamTask:
        policy, retrieval_failed = self._policy(case["tenant_id"], case["subject"], entry.manifest.knowledge_scope)
        current = {"case_id": str(case["case_id"]), "customer_id": str(case["customer_id"]), "status": str(case["status"]),
                   "version": case["version"], "intent": case.get("intent"), "issue_code": case.get("issue_code"),
                   "sentiment": case.get("sentiment"), "owner_team_id": case.get("owner_team_id")}
        current["request_id"] = request_id_for_case(case)
        inputs = ContextInputs(case_id=case["case_id"], tenant_id=case["tenant_id"], team_id=entry.manifest.team_id,
                               knowledge_scope=entry.manifest.knowledge_scope, system_instruction="Answer using the supplied evidence.",
                               current_state=current, policy_chunks=policy, history_entries=[], retrieval_failed=retrieval_failed)
        context = self.context_broker.build(inputs)
        return TeamTask(task_id=uuid4(), run_id=run_id, case_id=case["case_id"], team_id=entry.manifest.team_id,
                        capability=self._capability(case), case_version=case["version"], input_text=case["subject"], context=context,
                        allowed_tools=entry.manifest.allowed_tools, deadline_at=datetime.now(UTC) + timedelta(seconds=get_guardrails().get("reliability.team_timeout_seconds")),
                        resume=resume, resume_node=resume_node)

    def _transition_with_retry(self, conn, *, tenant_id: str, case_id: UUID, event_type: EventType,
                               payload: dict[str, Any], actor_id: str, expected_version: int):
        attempts = get_guardrails().get("concurrency.max_recompute_attempts")
        version = expected_version
        for attempt in range(attempts + 1):
            try:
                return transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=version,
                                       event_type=event_type, payload=payload, actor_type="controller", actor_id=actor_id)
            except StateConflict:
                if attempt >= attempts:
                    raise
                latest = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
                if latest is None:
                    raise
                version = latest["version"]

    async def run_case(self, *, tenant_id: str, case_id: UUID, actor_id: str = "controller") -> dict[str, Any]:
        started = time.monotonic()
        with self.connection_factory() as conn:
            case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
            if case is None:
                raise ControllerError("case not found")
            with conn.transaction():
                run_id = self.case_service.start_run(conn, tenant_id=tenant_id, case_id=case_id)
                if case["status"] == CaseStatus.ROUTING:
                    try:
                        intent = case.get("intent")
                        entry = self.registry.resolve(case_type=intent or "", intent=intent)
                        capability = self.registry.capability_for(entry, intent)
                        self._transition_with_retry(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                                    event_type=EventType.ROUTED, payload={"owner_team_id": entry.manifest.team_id, "capability": capability}, actor_id=actor_id)
                    except RegistryError as exc:
                        self._transition_with_retry(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                                    event_type=EventType.ROUTING_FAILED, payload={"failure_code": "no_team"}, actor_id=actor_id)
                        self.case_service.finish_run(conn, run_id, "failed")
                        return {"case_id": str(case_id), "status": "escalated", "run_id": str(run_id), "error": str(exc)}
                    case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
                else:
                    entry = self.registry.get(case["owner_team_id"])
                resume = False
                resume_node = None
                if case["status"] == CaseStatus.RESUMING:
                    wait_reason = (case.get("state_json") or {}).get("wait_reason", "customer_input")
                    resume_node = RESUME_NODE_FOR_WAIT[wait_reason]
                    transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                    event_type=EventType.RESUMED, payload={"resume_node": resume_node},
                                    actor_type="controller", actor_id=actor_id)
                    case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
                    resume = True
                if time.monotonic() - started > get_guardrails().get("reliability.case_wall_clock_seconds"):
                    transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                    event_type=EventType.GUARDRAIL_ESCALATED,
                                    payload={"guardrail": "case_wall_clock_seconds", "observed": time.monotonic() - started},
                                    actor_type="controller", actor_id=actor_id)
                    self.case_service.finish_run(conn, run_id, "failed")
                    return {"case_id": str(case_id), "run_id": str(run_id), "status": "escalated"}
                task = self._task(case, entry, run_id, resume=resume, resume_node=resume_node)
                self.case_service.checkpoint(case_id=case_id, run_id=run_id, node_name="team.execute", runtime_state={"case_version": case["version"]})
                try:
                    result: TeamResult = await asyncio.wait_for(self.team_executor.execute(task), timeout=get_guardrails().get("reliability.team_timeout_seconds"))
                except asyncio.TimeoutError:
                    transition = transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                                 event_type=EventType.GUARDRAIL_ESCALATED,
                                                 payload={"guardrail": "team_timeout_seconds", "observed": get_guardrails().get("reliability.team_timeout_seconds")},
                                                 actor_type="controller", actor_id=actor_id)
                    self.case_service.finish_run(conn, run_id, "failed")
                    return {"case_id": str(case_id), "run_id": str(run_id), "status": transition.status.value, "version": transition.version}
                # ★대조에는 **Controller 가 만든** task.context 를 넘긴다.
                #   Team 이 돌려준 result.context 를 쓰면 근거와 제안을 같은 쪽이 지어낼 수 있어
                #   대조가 순환한다. 위조할 수 없는 쪽으로 잰다.
                result = await self._maybe_review(task, result)
                transition = self._apply_result(conn, case, run_id, result, actor_id, context=task.context)
                self.case_service.finish_run(conn, run_id, "succeeded")
                return {"case_id": str(case_id), "run_id": str(run_id), "status": transition.status.value, "version": transition.version,
                        "next_action": result.next_action.value, "resume_token": getattr(self, "_last_token", None)}

    def _apply_result(self, conn, case: dict[str, Any], run_id: UUID, result: TeamResult, actor_id: str,
                      *, context: Any = None):
        event, payload, outbox = self._event_for_result(conn, case, result, context=context)
        return transition_case(conn, tenant_id=case["tenant_id"], case_id=case["case_id"], expected_version=case["version"],
                               event_type=event, payload=payload, actor_type="controller", actor_id=actor_id, outbox=outbox)

    async def _maybe_review(self, task: TeamTask, result: TeamResult) -> TeamResult:
        """Run the configured post-generation review pass, if enabled."""
        config = self.response_review
        if not config or not config.enabled or not result.answer:
            return result
        entry = self.registry.get(config.owner_team_id)
        manifest = entry.manifest
        context = task.context.model_copy(update={
            "team_id": manifest.team_id,
            "knowledge_scope": manifest.knowledge_scope,
            "current_state": {**task.context.current_state, "answer": result.answer},
        })
        review_task = TeamTask(
            task_id=uuid4(), run_id=task.run_id, case_id=task.case_id,
            team_id=manifest.team_id,
            capability=self.registry.capability_for(entry, "response.generate_review"),
            case_version=task.case_version, input_text=result.answer,
            context=context, allowed_tools=manifest.allowed_tools,
            deadline_at=task.deadline_at,
        )
        return await asyncio.wait_for(
            self.team_executor.execute(review_task),
            timeout=get_guardrails().get("reliability.team_timeout_seconds"),
        )

    def _reject_unverified(self, conn, case: dict[str, Any], result: TeamResult, context: Any = None):
        """제안이 사실과 어긋나면 폐기하고 escalated 로 보낸다 (v7 §9-E).

        ★조용히 무시하지 않는다. 실패한 필드와 기대값·실제값의 **hash** 를 남긴다.
          원문을 남기면 결제 식별자·금액이 감사 로그로 새어 나간다(설계 원칙 §1).

        통과하면 None 을 돌려주고 호출자가 원래 경로를 계속한다.
        """
        # ★degraded Context 는 그 자체로 자동 실행 금지다 (v7 §9-E, DoD-25).
        #   Team 이 스스로 걸러 주기를 기대하지 않는다 — 새 Team 이 빠뜨리면 막을 수 없다.
        #   Controller 가 만든 context 를 먼저 보고, 없으면 Team 이 돌려준 것이라도 본다.
        pack = context if context is not None else getattr(result, "context", None)
        if getattr(pack, "degraded", False) and result.action_proposals:
            return EventType.GUARDRAIL_ESCALATED, {
                "guardrail": "degraded_context_blocks_action",
                "observed": ["ContextPack.degraded=true 상태에서 나온 제안은 자동 실행하지 않는다"],
            }, []

        # ★대조 선언이 없으면 대조하지 않는다. 도메인을 안 붙인 basement 상태다.
        if not self.fact_queries and not self.verification_policy.references:
            return None

        all_mismatches: list[Mismatch] = []
        failed_types: list[str] = []
        # ★근거는 **ContextPack** 의 evidence 로 센다 (v7 §9-E).
        #   result.evidence 로 재면 Team 이 근거와 제안을 둘 다 지어낼 수 있어 순환한다.
        # ★폴백을 두지 않는다. ContextPack 이 있으면 그것만이 근거의 출처다.
        #   처음엔 `pack_evidence or result.evidence` 로 짰는데, ContextPack 에 근거가
        #   하나도 없을 때 Team 이 스스로 만든 근거로 넘어가 **방어가 통째로 풀렸다.**
        #   근거가 없는 Context 면 근거를 든 제안은 전부 거부가 맞다.
        if pack is not None:
            evidence_ids = [e.evidence_id for e in getattr(pack, "evidence", [])]
        else:
            evidence_ids = [e.evidence_id for e in result.evidence]
        for proposal in result.action_proposals:
            mismatches = check_proposal(
                conn, tenant_id=case["tenant_id"], customer_id=case["customer_id"],
                proposal=proposal, evidence_ids=evidence_ids,
                policy=self.verification_policy, queries=self.fact_queries)
            if mismatches:
                all_mismatches.extend(mismatches)
                failed_types.append(proposal.action_type)

        if not all_mismatches:
            return None

        audit = audit_payload(action_type=",".join(failed_types), mismatches=all_mismatches,
                              case_id=case["case_id"], run_id=result.run_id, task_id=result.task_id)
        return EventType.GUARDRAIL_ESCALATED, {
            "guardrail": "action_proposal_verification_failed",
            "observed": [describe(all_mismatches)],
            "state_patch": {"rejected_proposal_audit": audit},
        }, []

    def _event_for_result(self, conn, case: dict[str, Any], result: TeamResult, *, context: Any = None):
        na = result.next_action
        if na is NextAction.RESPOND:
            return EventType.COMPLETED, {"answer_ref": str(uuid4()), "state_patch": {"answer": result.answer, "evidence": [e.model_dump(mode="json") for e in result.evidence]}}, []
        if na is NextAction.WAIT_FOR_INPUT:
            token = self.case_service.new_resume_token(); self._last_token = token
            metadata = self.case_service.resume_metadata(token, "customer_input")
            metadata["required_input_schema"] = result.required_input_schema
            return EventType.MISSING_INPUT, {"required_input_schema": result.required_input_schema, "state_patch": metadata}, []
        if na is NextAction.WAIT_FOR_APPROVAL:
            # ★v7 §9-E — 제안을 실행 경로에 넣기 전에 **사실과 대조**한다.
            #   전에는 proposal.arguments 를 그대로 action_requests 로 넣었다.
            #   실제 결제액이 30,000원인데 "50,000원 환불" 을 제안해도 통과했다.
            #   프롬프트가 아니라 코드가 방어선이다.
            blocked = self._reject_unverified(conn, case, result, context)
            if blocked is not None:
                return blocked

            action_ids = []
            for proposal in result.action_proposals:
                # The Team value is advisory. The server owns the final key at the write boundary.
                server_key = idempotency_key(
                    tenant_id=case["tenant_id"], request_id=request_id_for_case(case),
                    action_type=proposal.action_type, business_subject=str(case["case_id"]),
                )
                action_ids.append(str(self.repository.create_action_request(conn, tenant_id=case["tenant_id"], case_id=case["case_id"], action_type=proposal.action_type,
                    arguments=proposal.arguments, idempotency_key=server_key, status="pending_approval")))
            return EventType.APPROVAL_REQUIRED, {"action_id": action_ids[0], "state_patch": {"action_ids": action_ids}}, []
        if na is NextAction.ESCALATE:
            guardrail = result.failure_code or "team_escalated"
            return EventType.GUARDRAIL_ESCALATED, {"guardrail": guardrail, "observed": result.warnings or [guardrail]}, []
        raise ControllerError(f"unsupported result action: {na.value}")

    async def resume(self, *, tenant_id: str, case_id: UUID, token: str, actor_id: str = "controller", event_id: str | None = None) -> dict[str, Any]:
        with self.connection_factory() as conn:
            case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
            if case is None:
                raise ControllerError("case not found")
            try:
                if self.case_service.validate_resume(case, token, event_id=event_id) == "idempotent":
                    return {"case_id": str(case_id), "status": case["status"], "version": case["version"], "idempotent": True}
            except ResumeTokenError as exc:
                try:
                    with conn.transaction():
                        transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"], event_type=EventType.WAIT_EXPIRED,
                                        payload={"wait_reason": (case.get("state_json") or {}).get("wait_reason", "customer_input")}, actor_type="controller", actor_id=actor_id)
                    # The connection context may roll back when the original
                    # token error is re-raised. Make the escalation durable.
                    conn.commit()
                except InvalidTransition:
                    logger.warning(
                        "stale resume token ignored for terminal/non-waiting case",
                        extra={"tenant_id": tenant_id, "case_id": str(case_id), "event_type": EventType.WAIT_EXPIRED.value},
                    )
                raise ControllerError(str(exc)) from exc
            try:
                with conn.transaction():
                    wait_reason = (case.get("state_json") or {}).get("wait_reason", "customer_input")
                    node = RESUME_NODE_FOR_WAIT[wait_reason]
                    self._transition_with_retry(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"], event_type=EventType.VALID_INPUT,
                                                payload={"resume_token_hash": self.case_service.token_hash(token), "state_patch": {"resume_token_used": True, "last_resume_event_id": event_id}}, actor_id=actor_id)
                    latest = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
                    transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=latest["version"], event_type=EventType.RESUMED,
                                    payload={"resume_node": node}, actor_type="controller", actor_id=actor_id)
            except InvalidTransition:
                # A valid token can still race with another transition after
                # validation. The savepoint rolls back any partial resume;
                # record the stale attempt and leave the winning state intact.
                logger.warning(
                    "stale resume transition ignored",
                    extra={"tenant_id": tenant_id, "case_id": str(case_id), "event_type": EventType.RESUMED.value},
                )
                latest = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id) or case
                return {"case_id": str(case_id), "status": latest["status"], "version": latest["version"], "stale": True}
        return await self.run_case(tenant_id=tenant_id, case_id=case_id, actor_id=actor_id)
