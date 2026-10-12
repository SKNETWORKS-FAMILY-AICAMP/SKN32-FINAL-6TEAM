"""Case execution loop: route, build context, execute a Team, then transition."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import UUID, uuid4

from app.core.actions import ActionConflict, ActionHandlers, ActionRejected
from app.core.context import ContextBroker, ContextInputs
from app.core.contracts import CaseStatus, InvalidTransition, NextAction, TeamTask, TeamResult, RESUME_NODE_FOR_WAIT, StateConflict
from app.core.idempotency import idempotency_key, request_id_for_case
from app.core.registry import TeamRegistry, RegistryError
from app.core.settings import get_guardrails
from app.core.transition import OutboxMessage, transition_case
from app.core.case_lifecycle.events import EventType
from app.core.verification import Mismatch
from app.application.case_service import CaseService, ResumeRequestConflict, ResumeTokenError, ResumeTokenExpired
from app.core.redaction import masked
from app.application.proposal_guard import audit_payload, check_proposal, describe
from app.application.routing import case_type_of


class ControllerError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def _plain(value: Any) -> Any:
    """DB(jsonb)에 실릴 모양으로 — UUID·시각이 문자열이 된 값끼리 견준다."""
    import json

    return json.loads(json.dumps(value, ensure_ascii=False, default=str))

#: `run_case` 가 Team 을 부를 수 있는 상태. 그 밖(끝난 Case · 사람·고객·바깥을 기다리는 Case)은
#: 부르지 않고 그대로 돌려준다 — 기다림을 푸는 것은 승인 API 와 `resume()` 이다.
RUNNABLE_STATUSES = frozenset({CaseStatus.NEW, CaseStatus.CLASSIFYING, CaseStatus.ROUTING,
                               CaseStatus.RUNNING, CaseStatus.RESUMING})
ResumeRoute = Callable[[dict[str, Any], str], str | dict[str, Any] | None]


class Controller:
    def __init__(self, registry: TeamRegistry, *, context_broker: ContextBroker | None = None,
                 policy_search: Callable[..., list[Any]] | None = None,
                 connection_factory: Callable | None = None, repository: Any | None = None,
                 case_service: CaseService | None = None, graph_revision: str = "controller-v1",
                 team_executor: Any | None = None, broker: Any | None = None,
                 verification_policy: Any | None = None, fact_queries: Any = (),
                 response_review: Any | None = None,
                 action_handlers: ActionHandlers | None = None,
                 reroute: Callable[..., dict[str, Any] | None] | None = None) -> None:
        # ★대조 어휘는 주입받는다. Controller 는 어떤 필드를 대조하는지 모른다 —
        #   알면 basement 가 특정 업무 도메인에 묶인다.
        from app.core.verification import VerificationPolicy
        self.verification_policy = verification_policy or VerificationPolicy()
        # ★라우팅이 어긋났을 때 한 번 더 고르는 자리(`_reroute_once`). 안 꽂으면 종전대로 escalated.
        self.reroute = reroute
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
        # ★적용기는 조립이 넣는다. 없으면 **빈 표** — 승인 없는 제안은 전부 escalated 로 간다.
        self.action_handlers = action_handlers or ActionHandlers()

    #: ★Team 이 볼 수 있는 Case 상태 칸 — **이름이 중립인 것만.** 무엇을 가리키는지는
    #:  도메인이 채운다(`[결정 2026-09-17]` wiki `external/rest-endpoints.md` subject_ref).
    TEAM_STATE_KEYS = ("subject_ref", "trigger_source", "trigger", "interpretation",
                       "customer_input", "customer_input_history", "required_input_schema")

    @classmethod
    def _team_state(cls, case: dict[str, Any]) -> dict[str, Any]:
        state = case.get("state_json") or {}
        return {key: state[key] for key in cls.TEAM_STATE_KEYS if state.get(key) is not None}

    @staticmethod
    def _wait_reason(case: dict[str, Any]) -> str:
        """★`wait_reason` 을 안 적던 때(2026-09-18 전) 승인 대기에 들어간 Case 는 제안 id 로 알아본다."""
        state = case.get("state_json") or {}
        return state.get("wait_reason") or ("human_approval" if state.get("action_ids") else "customer_input")

    @classmethod
    def _capability_state(cls, case: dict[str, Any]) -> dict[str, Any]:
        """capability 선택에 넘기는 상태. ★`[2026-09-18]` 분류 결과 `issue_code` 도 싣는다 —
        한 Team 안에서 capability 를 가를 수 있는 것이 그것뿐인 모듈이 있다. 전에는 그런 Team 이
        어떤 요청이든 기본 capability 로만 불렸다(경위: wiki/records/reports/debugs/2026-09-17_1450 §6)."""
        state = cls._team_state(case)
        if case.get("issue_code"):
            state["issue_code"] = case["issue_code"]
        return state

    @staticmethod
    def _case_type(case: dict[str, Any]) -> str:
        state = case.get("state_json") or {}
        return case_type_of(case.get("issue_code"), fallback=case.get("intent"),
                            hint=state.get("routing_hint"),
                            hint_wins=bool(state.get("routing_hint_verified")))

    def _reroute_once(self, case: dict[str, Any], *, intent: str | None, failure: str):
        """라우팅이 어긋났을 때 **한 번만** 다시 고른다. (팀, capability, 기록) 또는 None. `[2026-10-06]`

        ★왜 있나. 이 제품에는 사람 운영자 큐가 없다 — `escalated` 로 끝내면 그 Case 는 아무도
          받지 않는다. 그래서 「받는 팀이 없다」를 **마지막 답이 아니라 한 번 더 묻는 자리**로 둔다.

        ★Controller 는 어느 팀이 무엇을 받는지 모른다. 재배분기는 주입받고, 코어는 **등록된
          팀 목록을 있는 그대로 넘겨** 준다(도메인 어휘를 해석하지 않는다).

        ★**지어내지 않는다.** 돌려받은 종류로 `Registry.resolve` 에 **다시 묻고**, 거기서도 팀이
          안 나오면 None 이다 — 모델이 없는 팀 이름을 내도 그대로 통과하지 않는다.
        ★**한 번만** 한다. 되풀이하면 모르는 Case 하나가 모델 호출을 무한히 쓴다.
        """
        if self.reroute is None:
            return None
        teams = [{"team_id": m.team_id, "accepts": sorted(m.accepted_case_types),
                  "capabilities": sorted(m.capabilities)}
                 for m in self.registry.manifests() if m.active]
        try:
            picked = self.reroute(subject=case.get("subject") or "", case_type=self._case_type(case),
                                  intent=intent, teams=teams, failure=failure)
        except Exception:                                   # noqa: BLE001 — 재배분이 죽어도 Case 는 종전대로 escalated 로 간다
            logger.exception("reroute failed for case %s", case.get("case_id"))
            return None
        if not picked or not picked.get("case_type"):
            return None
        chosen_type, chosen_intent = str(picked["case_type"]), picked.get("intent") or intent
        try:
            entry = self.registry.resolve(case_type=chosen_type, intent=chosen_intent)
            capability = self.registry.capability_for(entry, chosen_intent, input_text=case.get("subject"),
                                                      state=self._capability_state(case))
        except RegistryError:
            return None                                     # 모델이 고른 것도 받는 팀이 없다 — 여기서 끝낸다
        return entry, capability, {"from": self._case_type(case), "to": chosen_type,
                                   "intent": chosen_intent, "why": picked.get("why"),
                                   "by": picked.get("by") or "reroute"}

    def _capability(self, case: dict[str, Any]) -> str:
        """Return the capability selected by the injected Team registry."""
        intent = case.get("intent")
        owner = case.get("owner_team_id")
        if owner:
            # 추가 답변으로 담당이 바뀌었으면 최초 분류보다 실제 배분 결과를 따른다.
            entry = self.registry.get(owner)
        else:
            entry = self.registry.resolve(case_type=self._case_type(case), intent=intent)
        return self.registry.capability_for(entry, intent,
                                            input_text=(case.get("state_json") or {}).get("customer_input") or case.get("subject"),
                                            state=self._capability_state(case))

    def _policy(self, tenant_id: str, query: str, scopes: list[str]) -> tuple[list[Any], bool]:
        try:
            return self.policy_search(tenant_id, query, scopes), False
        except Exception:
            # Retrieval failure is an explicit signal to ContextBroker, not an empty result.
            return [], True

    def _task(self, case: dict[str, Any], entry, run_id: UUID, *, resume: bool = False,
              resume_node: str | None = None, retrieval_failed: bool = False,
              capability: str | None = None) -> TeamTask:
        # ★`[결정 2026-09-17]` Team 이 정책 근거를 선언했을 때만 RAG 를 돈다.
        #   전에는 `required_context` 가 선언만 되고 읽히지 않아, 정책 문서가 필요 없는
        #   일(실시간 사실로 판단하는 일정 조정)도 결과 0건이면 degraded → 전부 사람에게 갔다.
        # ★`[2026-09-22]` 요구를 **capability 단위**로 좁혔다. Team 단위로는
        #   「취소 판정은 규정이 필요하고 일정 관리는 아니다」를 나눌 수 없어서, 09-17 에는
        #   Team 전체에서 `policy` 를 빼는 쪽으로 풀었고 그 바람에 취소·성립 판정도
        #   근거 없이 돌았다. 이제 Team 이 면제 목록을 선언한다
        #   (`TeamManifest.policy_optional_capabilities` · wiki `teams/team-contract/fields.md`).
        capability = capability or self._capability(case)          # ★재배분으로 정해진 기능이 있으면 그대로(`run_case` 가 넘긴다)
        policy_required = ("policy" in (entry.manifest.required_context or [])
                           and capability not in (entry.manifest.policy_optional_capabilities or []))
        if policy_required:
            policy, retrieval_failed = self._policy(case["tenant_id"], case["subject"], entry.manifest.knowledge_scope)
        else:
            policy, retrieval_failed = [], False
        current = {"case_id": str(case["case_id"]), "customer_id": str(case["customer_id"]), "status": str(case["status"]),
                   "version": case["version"], "intent": case.get("intent"), "issue_code": case.get("issue_code"),
                   "sentiment": case.get("sentiment"), "owner_team_id": case.get("owner_team_id")}
        current["request_id"] = request_id_for_case(case)
        current.update(self._team_state(case))
        inputs = ContextInputs(case_id=case["case_id"], tenant_id=case["tenant_id"], team_id=entry.manifest.team_id,
                               knowledge_scope=entry.manifest.knowledge_scope, system_instruction="Answer using the supplied evidence.",
                               current_state=current, policy_chunks=policy, history_entries=[], retrieval_failed=retrieval_failed,
                               policy_required=policy_required)
        input_text = case["subject"]
        if current.get("customer_input") is not None:
            current["original_request"] = case["subject"]
            reply = current["customer_input"]
            prefix = "원래 요청: "
            separator = "\n추가 답변: "
            available = 12000 - len(prefix) - len(separator) - len(reply)
            input_text = (prefix + input_text[:max(0, available)] + separator + reply)[-12000:]
        context = self.context_broker.build(inputs)
        return TeamTask(task_id=uuid4(), run_id=run_id, case_id=case["case_id"], team_id=entry.manifest.team_id,
                        # ★위에서 이미 고른 값을 쓴다 — 두 번 고르면 정책 판정에 쓴 capability 와
                        #   Team 이 실제로 받는 capability 가 갈릴 수 있다.
                        capability=capability, case_version=case["version"], input_text=input_text, context=context,
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

    def _abandon_run(self, conn, run_id: UUID) -> None:
        """실행을 실패로 닫는다. ★예외가 나도 이 기록은 반드시 남긴다.

        Team 호출 **전에** A 단계를 커밋하므로, 그 뒤 단계에서 예외가 나도
        `agent_runs` 행은 살아남는다 — 시도했다는 감사 기록이 남는 것이 이
        변경의 목적이다. 그러나 그 행을 `active` 로 둔 채 나가면 활성 실행
        유일성(INV-CS-RT-011)이 이 Case 를 **영원히** 막는다.
        전에는 트랜잭션이 통째로 롤백돼 행 자체가 사라졌기 때문에 이 문제가
        없었다 — 트랜잭션을 좁히면서 새로 생기는 책임이다.
        """
        try:
            with conn.transaction():
                self.case_service.finish_run(conn, run_id, "failed")
            conn.commit()
        except Exception:
            # ★조용히 넘기지 않는다. 커넥션 자체가 죽었으면 여기도 실패하는데,
            #   그때 원래 예외를 가려 버리면 진짜 원인을 못 찾는다.
            logger.exception("failed to close agent run after error", extra={"run_id": str(run_id)})

    async def run_case(self, *, tenant_id: str, case_id: UUID, actor_id: str = "controller") -> dict[str, Any]:
        """Case 하나를 실행한다.

        ★트랜잭션을 **세 토막**으로 나눈다 (2026-09-01,
          `wiki/records/reports/2026-09-01_S-RUNCASE-TX-NARROWING_리포트.md`).

              A. 시작 기록 · 라우팅 · 재개 전이   ← 짧은 트랜잭션. Team 을 부르기 전에 커밋
              B. Team 실행 · 리뷰 패스            ← **트랜잭션 밖.** 외부 네트워크가 여기 있다
              C. 결과 반영 · 실행 종료 기록       ← 다시 짧은 트랜잭션

          전에는 A~C 가 하나의 열린 트랜잭션이었고 그 안에서 OpenAI 응답을
          `await` 했다. 그동안 `customer_cases` 행이 UPDATE 잠금에 걸려 있어
          같은 Case 에 대한 다른 쓰기가 전부 막혔고, LLM 이 타임아웃하면
          `start_run()` 이 남긴 **실행 시작 기록까지 함께 롤백**됐다 —
          시도했다는 사실 자체가 사라졌다.
          `app/application/classification.py` 가 Case 생성 경로에서 이미 같은
          모양으로 고쳐져 있다(같은 결함 종류, v8 §3-A 결함 2).

        ★각 단계는 **자기 트랜잭션을 커밋하고 나간다.** 커밋하지 않으면 psycopg3
          가 다음 `conn.transaction()` 을 새 트랜잭션이 아니라 SAVEPOINT 로 열어
          (앞선 읽기가 이미 암묵 트랜잭션을 열어 놓기 때문이다) 경계를 좁힌
          효과가 통째로 사라진다. `resume()` 도 같은 이유로 명시적 commit 을 쓴다.
        """
        started = time.monotonic()
        with self.connection_factory() as conn:
            case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
            if case is None:
                raise ControllerError("case not found")
            if case["status"] not in RUNNABLE_STATUSES:
                # ★`[2026-09-20]` 끝났거나 기다리는 중인 Case 에는 Team 을 부르지 않는다. 전에는
                #   불러 놓고 결과를 쓸 때 상태기계가 `InvalidTransition` 으로 막았다 — 결과는 같지만
                #   LLM·도구를 한 번 더 쓰고, 실패 사유가 「전이 오류」로 보여 원인을 가린다.
                return {"case_id": str(case_id), "status": str(case["status"]), "version": case["version"],
                        "skipped": "not_runnable"}

            # ── A. 시작·라우팅·재개 ────────────────────────────────────────────
            rerouted_capability: str | None = None            # 재배분으로 새로 정한 기능 — 아래 B 의 `_task` 에 그대로 넘긴다
            with conn.transaction():
                run_id = self.case_service.start_run(conn, tenant_id=tenant_id, case_id=case_id)
                if case["status"] == CaseStatus.ROUTING:
                    try:
                        # ★두 축이다(v11 §5-B). `case_type` 은 대상 객체 종류로
                        #   `issue_code` 접두에서 나오고, `intent` 는 요청 종류다.
                        #   전에는 같은 값을 둘 다에 넣었다 — 커머스에서는 두 축이
                        #   우연히 같은 말이라 맞았지만, 여행에서는 요청 종류 다섯이
                        #   여섯 팀 어느 것과도 안 맞아 **아무 데도 도달하지 못했다.**
                        intent = case.get("intent")
                        entry = self.registry.resolve(case_type=self._case_type(case), intent=intent)
                        # ★`_task()` 와 **같은 인자로** 고른다. 전에는 여기서만 `input_text` 없이
                        #   골라 ROUTED 이벤트의 capability 와 실제로 Team 에 준 것이 갈릴 수 있었다.
                        capability = self.registry.capability_for(
                            entry, intent, input_text=case.get("subject"), state=self._capability_state(case))
                        self._transition_with_retry(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                                    event_type=EventType.ROUTED, payload={"owner_team_id": entry.manifest.team_id, "capability": capability}, actor_id=actor_id)
                    except RegistryError as exc:
                        # ★`[2026-10-06]` **한 번 더 고른다.** 라우팅이 어긋났다고 곧바로 사람에게 넘기면
                        #   이 제품에서는 아무도 받지 않는다(운영자 큐가 없다 · 고객은 알림만 받는다).
                        #   재배분기는 **주입받는다** — Controller 는 어느 팀이 무엇을 받는지 모른다.
                        #   돌려받은 값으로 **Registry 에 다시 묻는다**(모델이 없는 팀을 내면 거부된다).
                        redirect = self._reroute_once(case, intent=intent, failure=str(exc))
                        if redirect is not None:
                            entry, capability, note = redirect
                            rerouted_capability = capability
                            self._transition_with_retry(
                                conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                event_type=EventType.ROUTED,
                                payload={"owner_team_id": entry.manifest.team_id, "capability": capability,
                                         "rerouted": note}, actor_id=actor_id)
                        else:
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
                    wait_reason = self._wait_reason(case)
                    resume_node = RESUME_NODE_FOR_WAIT[wait_reason]
                    transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                    event_type=EventType.RESUMED, payload={"resume_node": resume_node},
                                    actor_type="controller", actor_id=actor_id)
                    case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
                    resume = True
                    if wait_reason == "human_approval":
                        approved = self.repository.approved_pending_actions(conn, tenant_id=tenant_id,
                                                                            case_id=case_id)
                        # ★적용기가 **전부** 있을 때만 코어가 실행한다. 하나라도 없으면 예전처럼 Team 을
                        #   다시 부른다 — 적용기가 없는 도메인의 승인 흐름을 이 변경이 바꾸지 않게.
                        if approved and all(self.action_handlers.get(a["action_type"]) for a in approved):
                            # ★A 단계 트랜잭션 안이다 — 여기서 돌려주면 블록을 나가며 함께 커밋된다.
                            transition = self._apply_approved(conn, case, approved, actor_id)
                            self.case_service.finish_run(
                                conn, run_id, "succeeded" if transition.status == CaseStatus.RESOLVED else "failed")
                            return {"case_id": str(case_id), "run_id": str(run_id),
                                    "status": transition.status.value, "version": transition.version}
                if time.monotonic() - started > get_guardrails().get("reliability.case_wall_clock_seconds"):
                    transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                    event_type=EventType.GUARDRAIL_ESCALATED,
                                    payload={"guardrail": "case_wall_clock_seconds", "observed": time.monotonic() - started},
                                    actor_type="controller", actor_id=actor_id)
                    self.case_service.finish_run(conn, run_id, "failed")
                    return {"case_id": str(case_id), "run_id": str(run_id), "status": "escalated"}
            conn.commit()

            try:
                # ── B. Team 실행 — 여기서는 트랜잭션이 열려 있지 않다 ───────────
                #   `_task()` 의 RAG 검색도, `checkpoint()` 도 이 커넥션을 쓰지 않는다
                #   (checkpoint 는 순수 함수다 — DB 를 건드리지 않는다).
                task = self._task(case, entry, run_id, resume=resume, resume_node=resume_node, capability=rerouted_capability)
                self.case_service.checkpoint(case_id=case_id, run_id=run_id, node_name="team.execute", runtime_state={"case_version": case["version"]})
                try:
                    result: TeamResult = await asyncio.wait_for(self.team_executor.execute(task), timeout=get_guardrails().get("reliability.team_timeout_seconds"))
                except asyncio.TimeoutError:
                    with conn.transaction():
                        transition = transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"],
                                                     event_type=EventType.GUARDRAIL_ESCALATED,
                                                     payload={"guardrail": "team_timeout_seconds", "observed": get_guardrails().get("reliability.team_timeout_seconds")},
                                                     actor_type="controller", actor_id=actor_id)
                        self.case_service.finish_run(conn, run_id, "failed")
                    conn.commit()
                    return {"case_id": str(case_id), "run_id": str(run_id), "status": transition.status.value, "version": transition.version}
                # ★대조에는 **Controller 가 만든** task.context 를 넘긴다.
                #   Team 이 돌려준 result.context 를 쓰면 근거와 제안을 같은 쪽이 지어낼 수 있어
                #   대조가 순환한다. 위조할 수 없는 쪽으로 잰다.
                result = await self._maybe_review(task, result)

                # ── C. 결과 반영 ───────────────────────────────────────────────
                resume_token = (self.case_service.new_resume_token()
                                if result.next_action is NextAction.WAIT_FOR_INPUT else None)
                with conn.transaction():
                    transition = self._apply_result(conn, case, run_id, result, actor_id,
                                                    context=task.context, resume_token=resume_token)
                    self.case_service.finish_run(conn, run_id, "succeeded")
                conn.commit()
            except StateConflict:
                # ★Team 을 부르는 동안 다른 쓰기가 이 Case 를 바꿨다.
                #   **재계산 없이 재시도하지 않는다.** `_transition_with_retry` 는
                #   ROUTED·VALID_INPUT 처럼 payload 가 Case 내용에 의존하지 않는
                #   장부성 전이에만 쓴다. 결과 반영은 종류가 다르다 — 답변 문장과
                #   ActionProposal 은 우리가 읽은 스냅샷을 근거로 만들어졌고,
                #   version 이 밀렸다는 것은 그 근거가 더 이상 사실이 아닐 수
                #   있다는 **증거**다. 최신 version 만 갈아 끼워 같은 payload 를
                #   밀어 넣으면 확인하지 않은 상태 위에 답을 얹게 된다
                #   (CLAUDE.md §0.1 — 근거 없이 확정하지 않는다).
                #   이긴 쪽 상태를 그대로 두고 이 실행만 실패로 닫는다.
                #   `resume()` 이 같은 종류의 경합(InvalidTransition)을 다루는
                #   방식과 같다 — 지면 조용히 물러나고 기록을 남긴다.
                self._abandon_run(conn, run_id)
                logger.warning(
                    "concurrent write won during team execution; result not applied",
                    extra={"tenant_id": tenant_id, "case_id": str(case_id), "run_id": str(run_id)},
                )
                latest = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id) or case
                return {"case_id": str(case_id), "run_id": str(run_id), "status": latest["status"],
                        "version": latest["version"], "stale": True}
            except BaseException:
                # ★A 를 커밋했으므로 실행 시작 기록은 살아남는다. 그 대가로 실행을
                #   닫는 책임이 생긴다. CancelledError 도 포함해야 해서 BaseException 이다.
                self._abandon_run(conn, run_id)
                raise
            return {"case_id": str(case_id), "run_id": str(run_id), "status": transition.status.value, "version": transition.version,
                    "next_action": result.next_action.value, "resume_token": resume_token}

    def _apply_result(self, conn, case: dict[str, Any], run_id: UUID, result: TeamResult, actor_id: str,
                      *, context: Any = None, resume_token: str | None = None):
        # ★여기서는 `_transition_with_retry` 를 쓰지 않는다. 의도적이다 —
        #   `run_case()` 의 `except StateConflict` 주석에 이유를 적었다.
        event, payload, outbox = self._event_for_result(conn, case, result, context=context,
                                                       resume_token=resume_token)
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

    def _event_for_result(self, conn, case: dict[str, Any], result: TeamResult, *, context: Any = None,
                          resume_token: str | None = None):
        na = result.next_action
        if na is NextAction.RESPOND:
            state_patch: dict[str, Any] = {"answer": result.answer,
                                           "evidence": [e.model_dump(mode="json") for e in result.evidence],
                                           "decisions": [d.model_dump(mode="json") if hasattr(d, "model_dump") else d
                                                         for d in result.decisions]}
            outbox: list[OutboxMessage] = []
            # ★`[결정 2026-09-17]` 답과 함께 온 **승인 없는 제안**을 버리지 않는다.
            #   전에는 이 갈래가 제안을 보지 않아 조용히 사라졌다. 적용 조건은
            #   wiki `actions/approval.md` 「승인 없이 적용되는 제안」.
            auto = [p for p in result.action_proposals if not p.approval_required]
            if auto:
                blocked = self._reject_unverified(conn, case, result, context)
                if blocked is not None:
                    return blocked
                applied = self._apply_auto_proposals(conn, case, auto)
                if isinstance(applied, tuple):
                    return applied
                state_patch["applied_actions"] = [record for record, _ in applied]
                actual_answers = [record["answer"] for record, _ in applied if record.get("answer")]
                if actual_answers:
                    state_patch["answer"] = "\n".join(actual_answers)
                for _, messages in applied:
                    outbox.extend(messages)
            return EventType.COMPLETED, {"answer_ref": str(uuid4()), "state_patch": state_patch}, outbox
        if na is NextAction.WAIT_FOR_INPUT:
            token = resume_token or self.case_service.new_resume_token()
            metadata = self.case_service.resume_metadata(token, "customer_input")
            metadata["required_input_schema"] = result.required_input_schema
            metadata["answer"] = result.answer
            metadata["evidence"] = [e.model_dump(mode="json") for e in result.evidence]
            metadata["decisions"] = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d
                                     for d in result.decisions]
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
                # ★`[2026-09-18]` v11 §4-E — 적용기가 있으면 키의 대상은 **적용기가 인자에서 꺼낸 대상 id**다.
                #   Case id 로 두면 한 Case 가 서로 다른 대상 둘에 같은 종류의 제안을 낼 때 둘째가
                #   같은 키로 합쳐져 **조용히 사라진다**. 대상을 못 꺼내면 폴백하지 않고 사람에게 넘긴다.
                #   적용기가 없는 도메인은 예전 그대로(Case id).
                handler = self.action_handlers.get(proposal.action_type)
                subject = str(case["case_id"])
                if handler is not None:
                    try:
                        subject = handler.subject(proposal.arguments)
                    except ActionRejected as exc:
                        return self._escalation("action_rejected", str(exc))
                server_key = idempotency_key(
                    tenant_id=case["tenant_id"], request_id=request_id_for_case(case),
                    action_type=proposal.action_type, business_subject=subject,
                )
                # ★`[2026-09-20]` 적용기가 없어 키의 대상이 Case id 인 제안은 **둘째가 조용히 합쳐진다**
                #   (`ON CONFLICT … DO UPDATE` 가 같은 행을 돌려준다). 합치기 전에 인자가 같은지 보고,
                #   다르면 사람에게 넘긴다 — 제안 하나가 말없이 사라지지 않게. 같은 인자면 그대로 멱등이다.
                existing = self.repository.find_action_request(conn, tenant_id=case["tenant_id"],
                                                               idempotency_key=server_key)
                if existing is not None and existing.get("arguments") != _plain(proposal.arguments):
                    return self._escalation(
                        "action_key_collision",
                        f"{proposal.action_type}: 같은 멱등 키에 다른 인자의 제안이 이미 있다")
                action_ids.append(str(self.repository.create_action_request(conn, tenant_id=case["tenant_id"], case_id=case["case_id"], action_type=proposal.action_type,
                    arguments=proposal.arguments, idempotency_key=server_key, status="pending_approval")))
            # ★`[2026-09-18]` 무엇을 기다리는지 적는다. 전에는 안 적어 승인 뒤 재개가 기본값
            #   `customer_input` 으로 읽혀 재개 지점이 `validate_input` 이 됐다.
            return EventType.APPROVAL_REQUIRED, {"action_id": action_ids[0],
                                                 "state_patch": {"action_ids": action_ids,
                                                                 "wait_reason": "human_approval"}}, []
        if na is NextAction.ESCALATE:
            guardrail = result.failure_code or "team_escalated"
            return EventType.GUARDRAIL_ESCALATED, {"guardrail": guardrail, "observed": result.warnings or [guardrail]}, []
        raise ControllerError(f"unsupported result action: {na.value}")

    @staticmethod
    def _escalation(guardrail: str, observed: str):
        return EventType.GUARDRAIL_ESCALATED, {"guardrail": guardrail, "observed": [observed]}, []

    def _apply_auto_proposals(self, conn, case: dict[str, Any], proposals: list[Any]):
        """승인 없는 제안을 **한 savepoint 안에서 전부** 적용한다.

        하나라도 못 하면 전부 되돌리고 escalated 전이를 돌려준다 — 두 제안 중 하나만
        반영된 대상을 남기지 않는다. 성공하면 `[(기록, outbox 메시지들)]` 을 돌려준다.
        """
        class _Stop(Exception):
            def __init__(self, outcome):
                self.outcome = outcome

        applied: list[tuple[dict[str, Any], list[OutboxMessage]]] = []
        try:
            with conn.transaction():
                for proposal in proposals:
                    handler = self.action_handlers.get(proposal.action_type)
                    if handler is None:
                        raise _Stop(self._escalation(
                            "action_handler_missing", f"적용기가 없는 제안 종류: {proposal.action_type}"))
                    if not getattr(handler, "auto_apply", False) or proposal.risk_level != "low":
                        raise _Stop(self._escalation(
                            "action_requires_approval",
                            f"{proposal.action_type} 는 승인 없이 적용하지 않는다(risk={proposal.risk_level})"))
                    try:
                        subject = handler.subject(proposal.arguments)
                    except ActionRejected as exc:
                        raise _Stop(self._escalation("action_rejected", str(exc))) from exc
                    key = idempotency_key(tenant_id=case["tenant_id"], request_id=request_id_for_case(case),
                                          action_type=proposal.action_type, business_subject=subject)
                    existing = self.repository.find_action_request(conn, tenant_id=case["tenant_id"],
                                                                   idempotency_key=key)
                    if existing is not None and existing["status"] == "succeeded":
                        # ★같은 대상에 같은 요청이 이미 적용됐다 — 다시 적용하지 않는다.
                        record = {"action_id": str(existing["action_id"]), "action_type": proposal.action_type,
                                  "result_ref": existing["provider_ref"], "replayed": True}
                        prior_case = case
                        if existing.get("case_id", case["case_id"]) != case["case_id"]:
                            prior_case = self.repository.get_case(
                                conn, tenant_id=case["tenant_id"], case_id=existing["case_id"]) or {}
                        prior = next((r for r in (prior_case.get("state_json") or {}).get("applied_actions", [])
                                      if r.get("action_id") == record["action_id"]), {})
                        for field in ("summary", "answer"):
                            if field in prior:
                                record[field] = prior[field]
                        applied.append((record, []))
                        continue
                    try:
                        outcome = handler.apply(conn, tenant_id=case["tenant_id"],
                                                customer_id=case["customer_id"], case_id=case["case_id"],
                                                arguments=proposal.arguments)
                    except ActionConflict as exc:
                        raise _Stop(self._escalation("action_target_changed", str(exc))) from exc
                    except ActionRejected as exc:
                        raise _Stop(self._escalation("action_rejected", str(exc))) from exc
                    action_id = self.repository.create_action_request(
                        conn, tenant_id=case["tenant_id"], case_id=case["case_id"],
                        action_type=proposal.action_type, arguments=proposal.arguments,
                        idempotency_key=key, status="succeeded", provider_ref=outcome.result_ref)
                    # ★`[2026-09-22]` 실행 장부(v11 §12 DoD-20). 적을 것이 하나도 없으면 UPDATE 를
                    #   내지 않는다 — 장부 칸을 안 쓰는 적용기(일정 조정)의 경로를 건드리지 않는다.
                    ledger = outcome.ledger()
                    if any(value is not None for value in ledger.values()):
                        self.repository.set_action_status(
                            conn, tenant_id=case["tenant_id"], action_id=action_id,
                            status="succeeded", ledger=ledger)
                    record = {"action_id": str(action_id), "action_type": proposal.action_type,
                              "result_ref": outcome.result_ref, "summary": outcome.summary}
                    if outcome.answer is not None:
                        record["answer"] = outcome.answer
                    applied.append((record, list(outcome.outbox)))
        except _Stop as stop:
            return stop.outcome
        return applied

    def _apply_approved(self, conn, case: dict[str, Any], approved: list[dict[str, Any]], actor_id: str):
        """**승인된** 제안을 적용기로 실행한다(`[2026-09-18]`, wiki `actions/approval.md`).

        ★전에는 승인하면 Case 가 `resuming` → Team 재실행으로 갔고, Team 은 side effect 를 안 하니
          **아무것도 실행되지 않았다.** 실행은 코어가 한다 — Team 이 아니다(CLAUDE.md §0.2).
        ★한 savepoint 안에서 전부 — 하나라도 못 하면 전부 되돌리고 escalated.
        ★공급자 시간 초과·연결 오류는 성공으로 추정하지 않는다 — `unknown` 으로 남기고 재실행하지
          않는다(CLAUDE.md §0.2). 승인 직전 재검증은 승인 API 가 이미 했다(v7 §9-E).
        """
        applied: list[dict[str, Any]] = []
        outbox: list[OutboxMessage] = []
        failure: tuple[str, str, str] | None = None     # (guardrail, observed, action 상태)
        failed_action = None
        try:
            with conn.transaction():
                for action in approved:
                    handler = self.action_handlers.get(action["action_type"])
                    try:
                        outcome = handler.apply(conn, tenant_id=case["tenant_id"], customer_id=case["customer_id"],
                                                case_id=case["case_id"], arguments=action["arguments"])
                    except ActionConflict as exc:
                        failure, failed_action = ("action_target_changed", str(exc), "failed"), action
                        raise
                    except ActionRejected as exc:
                        failure, failed_action = ("action_rejected", str(exc), "failed"), action
                        raise
                    except (TimeoutError, ConnectionError) as exc:
                        failure, failed_action = ("action_provider_unknown", str(exc), "unknown"), action
                        raise
                    # ★`[2026-09-22]` 실행 장부를 같은 UPDATE 로 적는다(v11 §12 DoD-20) —
                    #   무엇을(action_type·인자)·왜(reason)·얼마에(amount_cents·출처)·되돌림 기한.
                    #   코어는 이 값들의 뜻을 모른다. 적용기가 채우고 여기서 그대로 싣는다.
                    self.repository.set_action_status(conn, tenant_id=case["tenant_id"],
                                                      action_id=action["action_id"], status="succeeded",
                                                      provider_ref=outcome.result_ref,
                                                      ledger=outcome.ledger())
                    applied.append({"action_id": str(action["action_id"]), "action_type": action["action_type"],
                                    "result_ref": outcome.result_ref, "summary": outcome.summary})
                    outbox.extend(outcome.outbox)
        except (ActionConflict, ActionRejected, TimeoutError, ConnectionError):
            guardrail, observed, status = failure
            self.repository.set_action_status(conn, tenant_id=case["tenant_id"],
                                              action_id=failed_action["action_id"], status=status)
            return transition_case(conn, tenant_id=case["tenant_id"], case_id=case["case_id"],
                                   expected_version=case["version"], event_type=EventType.GUARDRAIL_ESCALATED,
                                   payload={"guardrail": guardrail, "observed": [observed]},
                                   actor_type="controller", actor_id=actor_id)
        answer = "승인된 작업을 실행했습니다: " + ", ".join(a["action_type"] for a in applied)
        return transition_case(conn, tenant_id=case["tenant_id"], case_id=case["case_id"],
                               expected_version=case["version"], event_type=EventType.COMPLETED,
                               payload={"answer_ref": str(uuid4()),
                                        "state_patch": {"answer": answer, "applied_actions": applied}},
                               actor_type="controller", actor_id=actor_id, outbox=outbox)

    async def resume(self, *, tenant_id: str, case_id: UUID, token: str,
                     actor_id: str = "controller", event_id: str | None = None,
                     message: str | None = None, expected_version: int | None = None,
                     resume_route: ResumeRoute | None = None) -> dict[str, Any]:
        return await self._resume(tenant_id=tenant_id, case_id=case_id, token=token,
                                  actor_id=actor_id, event_id=event_id, message=message,
                                  expected_version=expected_version, resume_route=resume_route)

    async def resume_customer_input(self, *, tenant_id: str, case_id: UUID, customer_id: UUID,
                                     message: str, event_id: str, expected_version: int | None = None,
                                     actor_id: str = "controller",
                                     resume_route: ResumeRoute | None = None) -> dict[str, Any]:
        """인증된 웹 고객만 자신의 입력 대기를 재개한다. 공개 토큰 API와 분리한다."""
        return await self._resume(tenant_id=tenant_id, case_id=case_id, token=None,
                                  customer_id=customer_id, actor_id=actor_id, event_id=event_id,
                                  message=message, expected_version=expected_version, resume_route=resume_route)

    async def _resume(self, *, tenant_id: str, case_id: UUID, token: str | None,
                      actor_id: str, event_id: str | None, message: str | None,
                      expected_version: int | None, customer_id: UUID | None = None,
                      resume_route: ResumeRoute | None = None) -> dict[str, Any]:
        if message is not None and not message.strip():
            raise ValueError("customer input must not be blank")
        safe_message = masked(message.strip()) if message is not None else None
        message_hash = self.case_service.token_hash(message.strip()) if message is not None else None
        with self.connection_factory() as conn:
            # 같은 업무의 토큰 검증과 소비는 행 잠금 안에서 처리한다.
            # 읽기 뒤 버전만 재시도하면 다른 답변이 사용한 토큰을 다시 소비할 수 있다.
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM customer_cases WHERE tenant_id=%s AND case_id=%s FOR UPDATE",
                            (tenant_id, case_id))
            case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
            if case is None:
                raise ControllerError("case not found")
            if token is None and (customer_id is None or str(case["customer_id"]) != str(customer_id)):
                raise ControllerError("customer does not own case")
            try:
                validation = (self.case_service.validate_resume(case, token, event_id=event_id,
                                                                 message_hash=message_hash) if token is not None
                              else self.case_service.validate_customer_input(case, event_id=event_id,
                                                                              message_hash=message_hash))
                if validation == "idempotent":
                    return {"case_id": str(case_id), "status": case["status"],
                            "version": case["version"], "idempotent": True}
            except ResumeRequestConflict as exc:
                raise StateConflict(str(exc)) from exc
            except ResumeTokenExpired as exc:
                try:
                    with conn.transaction():
                        transition_case(conn, tenant_id=tenant_id, case_id=case_id,
                                        expected_version=case["version"], event_type=EventType.WAIT_EXPIRED,
                                        payload={"wait_reason": self._wait_reason(case)},
                                        actor_type="controller", actor_id=actor_id)
                    conn.commit()
                except InvalidTransition:
                    logger.warning("stale resume token ignored for terminal/non-waiting case",
                                   extra={"tenant_id": tenant_id, "case_id": str(case_id)})
                raise ControllerError(str(exc)) from exc
            except ResumeTokenError as exc:
                logger.warning("stale resume token ignored; waiting state preserved",
                               extra={"tenant_id": tenant_id, "case_id": str(case_id)})
                raise ControllerError(str(exc)) from exc
            if expected_version is not None and expected_version != case["version"]:
                raise StateConflict("case version changed before customer input")
            state = case.get("state_json") or {}
            token_hash = self.case_service.token_hash(token) if token is not None else state["resume_token_hash"]
            patch = {"resume_token_used": True, "last_resume_event_id": event_id}
            if safe_message is not None:
                patch["customer_input"] = safe_message
                patch["customer_input_history"] = [*state.get("customer_input_history", []), safe_message]
            if event_id:
                patch["resume_requests"] = [*state.get("resume_requests", []), {
                    "request_id": event_id, "message_hash": message_hash,
                    "token_hash": token_hash,
                }]
            try:
                with conn.transaction():
                    transition_case(conn, tenant_id=tenant_id, case_id=case_id,
                                    expected_version=case["version"], event_type=EventType.VALID_INPUT,
                                    payload={"resume_token_hash": token_hash,
                                             "state_patch": patch}, actor_type="controller", actor_id=actor_id)
                    if resume_route is not None and safe_message is not None:
                        latest = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
                        routing = resume_route(latest, safe_message)
                        route_patch = {}
                        if isinstance(routing, dict):
                            team_id = routing.get("owner_team_id") or latest["owner_team_id"]
                            route_patch = routing.get("state_patch", {})
                            if not isinstance(route_patch, dict):
                                raise ValueError("resume route state patch must be an object")
                            allowed = set(self.TEAM_STATE_KEYS) - {"customer_input", "customer_input_history"}
                            if set(route_patch) - allowed:
                                raise ValueError("resume route cannot change controller metadata")
                        else:
                            team_id = routing
                        if team_id is not None and not isinstance(team_id, str):
                            raise ValueError("resume route owner must be a team id")
                        if team_id and (team_id != latest["owner_team_id"] or route_patch):
                            entry = self.registry.get(team_id)
                            if not entry.manifest.active:
                                raise RegistryError("resume team is inactive")
                            routed_case = {**latest, "state_json": {**latest["state_json"], **route_patch}}
                            capability = self.registry.capability_for(
                                entry, latest.get("intent"), input_text=safe_message,
                                state=self._capability_state(routed_case))
                            transition_case(conn, tenant_id=tenant_id, case_id=case_id,
                                            expected_version=latest["version"], event_type=EventType.ROUTED,
                                            payload={"owner_team_id": team_id, "capability": capability,
                                                     "state_patch": route_patch},
                                            actor_type="controller", actor_id=actor_id)
                    # 실행 입구가 RESUMED를 기록해야 TeamTask.resume/재개 지점도 맞는다.
                conn.commit()
            except InvalidTransition:
                logger.warning("stale resume transition ignored",
                               extra={"tenant_id": tenant_id, "case_id": str(case_id)})
                latest = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id) or case
                return {"case_id": str(case_id), "status": latest["status"],
                        "version": latest["version"], "stale": True}
        return await self.run_case(tenant_id=tenant_id, case_id=case_id, actor_id=actor_id)
