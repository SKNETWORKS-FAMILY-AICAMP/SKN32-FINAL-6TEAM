"""A-COP 계약 모델.

★이 파일은 `docs/handoff/01_계약_Pydantic.md` 의 구현체다.
  둘이 어긋나면 결함이다. 바꿀 때는 계약 문서를 먼저 고친다(RULE.md §3.5).

기준선: ../A-COP_구현계획서_v5.md §7
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ─────────────────────────────────────────────────────────────────────
# 예외 (계약 문서 §10)
# ★예외를 삼키지 않는다. 폴백 금지(RULE.md §3.2).
# ─────────────────────────────────────────────────────────────────────


class StateConflict(Exception):
    """optimistic concurrency 실패 — UPDATE affected row 가 0이다."""


class ContractViolation(Exception):
    """계약 검증 실패."""


class ToolNotAllowed(Exception):
    """TeamManifest.allowed_tools 밖의 tool 호출."""


class GuardrailExceeded(Exception):
    """step / tool / token / cost 상한 초과."""


class ScopeDenied(Exception):
    """scope 부족 또는 ownership 불일치."""


class InvalidTransition(Exception):
    """상태표에 없는 전이."""


# ─────────────────────────────────────────────────────────────────────
# Enum (계약 문서 §1 / v5 §5-1)
# ─────────────────────────────────────────────────────────────────────


class CaseStatus(str, Enum):
    NEW = "new"
    CLASSIFYING = "classifying"
    ROUTING = "routing"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_EXTERNAL = "waiting_external"
    RESUMING = "resuming"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NextAction(str, Enum):
    CONTINUE = "continue"
    WAIT_FOR_INPUT = "wait_for_input"
    WAIT_FOR_APPROVAL = "wait_for_approval"
    CALL_TOOL = "call_tool"
    HANDOFF = "handoff"
    RESPOND = "respond"
    ESCALATE = "escalate"


WaitReason = Literal["customer_input", "human_approval", "external_callback"]
ResumeNode = Literal["validate_input", "execute_approved_action", "verify_external_result"]

# wait_reason ↔ resume_node 는 1:1 이다 (v5 §5-4)
RESUME_NODE_FOR_WAIT: dict[str, str] = {
    "customer_input": "validate_input",
    "human_approval": "execute_approved_action",
    "external_callback": "verify_external_result",
}


# ─────────────────────────────────────────────────────────────────────
# Evidence (계약 문서 §2)
# ─────────────────────────────────────────────────────────────────────


class Evidence(BaseModel):
    """모든 주장에 붙는 출처.

    ★source_type · source_id · observed_at 은 의무다.
      근거 없는 문장을 답변에 넣지 않는다(CLAUDE.md §0.1).
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    # ★`remote_agent` 는 v7 에서 추가했다. A2A 로 위임한 원격 Team 이 돌려준 근거다.
    #   `tool_result` 로 뭉개면 **우리 시스템이 확인한 사실**과
    #   **남의 시스템이 그렇다고 말한 것**이 구분되지 않는다 — 신뢰도가 다르다.
    #   근거 대조(§9-E)에서도 원격 출처는 다르게 다뤄야 한다.
    source_type: Literal["customer_message", "db", "policy", "tool_result", "case_event",
                         "remote_agent"]
    source_id: str
    claim: str
    value: Any
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime


# ─────────────────────────────────────────────────────────────────────
# ContextPack (계약 문서 §3 / v5 §7-2, §9-1)
# ─────────────────────────────────────────────────────────────────────


class ContextPack(BaseModel):
    """Context Broker 가 예산 안에서 조합한 근거 묶음.

    ★token_budget=12000 의 근거는 모델 context window 한계가 아니다.
      (1) 건당 LLM 비용 통제 (2) lost-in-the-middle 품질 저하 완화 (3) 실험 재현성.
      다른 이유를 문서·주석에 쓰지 않는다.
    """

    model_config = ConfigDict(extra="forbid")

    pack_id: UUID
    case_id: UUID
    team_id: str
    tenant_id: str
    knowledge_scope: list[str]
    current_state: dict[str, Any]
    evidence: list[Evidence] = Field(default_factory=list, max_length=40)
    history_summary: str = Field(default="", max_length=10000)
    similar_cases: list[dict[str, Any]] = Field(default_factory=list, max_length=3)
    token_budget: Literal[12000] = 12000
    estimated_input_tokens: int = Field(ge=0)
    degraded: bool = False
    omissions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _budget_and_signals(self) -> ContextPack:
        # 예산을 넘긴 팩은 애초에 만들어지면 안 된다 (deterministic truncation 이 선행한다)
        if self.estimated_input_tokens > self.token_budget:
            raise ValueError(
                f"ContextPack 이 예산을 넘었다: {self.estimated_input_tokens} > {self.token_budget}. "
                "Context Broker 가 절삭한 뒤에 만들어야 한다."
            )
        # ★신호 없는 축소는 폴백이다(RULE.md §3.2). degraded 면 무엇을 뺐는지 남긴다.
        if self.degraded and not self.omissions:
            raise ValueError("degraded=True 인데 omissions 가 비었다. 무엇을 뺐는지 남겨야 한다.")
        return self


# ─────────────────────────────────────────────────────────────────────
# TeamTask (계약 문서 §4)
# ─────────────────────────────────────────────────────────────────────


class TeamTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_name: Literal["a_cop.team_task"] = "a_cop.team_task"
    contract_version: Literal["1.0"] = "1.0"
    task_id: UUID
    run_id: UUID
    case_id: UUID
    team_id: str
    capability: str
    case_version: int
    input_text: str = Field(min_length=1, max_length=12000)
    context: ContextPack
    allowed_tools: list[str]
    deadline_at: datetime
    resume: bool = False
    resume_node: ResumeNode | None = None

    @model_validator(mode="after")
    def _resume_consistency(self) -> TeamTask:
        if self.resume and self.resume_node is None:
            raise ValueError("resume=True 이면 resume_node 가 있어야 한다.")
        if not self.resume and self.resume_node is not None:
            raise ValueError("resume=False 인데 resume_node 가 있다.")
        if self.context.case_id != self.case_id:
            raise ValueError("ContextPack.case_id 가 TeamTask.case_id 와 다르다.")
        if self.context.team_id != self.team_id:
            raise ValueError("ContextPack.team_id 가 TeamTask.team_id 와 다르다.")
        return self


# ─────────────────────────────────────────────────────────────────────
# ActionProposal (계약 문서 §5)
# ─────────────────────────────────────────────────────────────────────


class ActionProposal(BaseModel):
    """Team 이 내는 제안. ★Team 은 side effect 를 실행하지 않는다(CLAUDE.md §0.2).

    idempotency_key 는 Team 이 제안한 값이 아니라 서버가 재계산한 값이 최종이다
    (sha256(tenant_id + request_id + action_type + business_subject), v5 §10-1).
    """

    model_config = ConfigDict(extra="forbid")

    action_type: str
    arguments: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=128)
    approval_required: bool
    risk_level: Literal["low", "medium", "high"]
    rationale_evidence_ids: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────
# TeamResult (계약 문서 §6)
# ─────────────────────────────────────────────────────────────────────


class TeamResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_name: Literal["a_cop.team_result"] = "a_cop.team_result"
    contract_version: Literal["1.0"] = "1.0"
    task_id: UUID
    run_id: UUID
    team_id: str
    outcome: Literal["completed", "waiting", "handoff", "escalated", "failed"]
    answer: str | None = Field(default=None, max_length=6000)
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    action_proposals: list[ActionProposal] = Field(default_factory=list)
    next_action: NextAction
    wait_reason: WaitReason | None = None
    required_input_schema: dict[str, Any] | None = None
    handoff_capability: str | None = None
    failure_code: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _next_action_consistency(self) -> TeamResult:
        na = self.next_action

        if na is NextAction.WAIT_FOR_INPUT:
            if self.wait_reason != "customer_input":
                raise ValueError("wait_for_input 은 wait_reason='customer_input' 이어야 한다.")
            if self.required_input_schema is None:
                raise ValueError("wait_for_input 은 required_input_schema 가 있어야 한다.")

        elif na is NextAction.WAIT_FOR_APPROVAL:
            if self.wait_reason != "human_approval":
                raise ValueError("wait_for_approval 은 wait_reason='human_approval' 이어야 한다.")
            if not self.action_proposals:
                raise ValueError("wait_for_approval 은 action_proposals 가 최소 1건 있어야 한다.")

        elif na is NextAction.HANDOFF:
            if not self.handoff_capability:
                raise ValueError("handoff 는 handoff_capability 가 있어야 한다.")

        elif na is NextAction.RESPOND:
            if not self.answer:
                raise ValueError("respond 는 answer 가 있어야 한다.")

        elif na is NextAction.ESCALATE:
            if not self.failure_code and not self.warnings:
                raise ValueError("escalate 는 failure_code 또는 warnings 가 있어야 한다.")

        # ★근거 없는 답변 금지 (CLAUDE.md §0.1)
        if self.answer and not self.evidence:
            raise ValueError(
                "answer 가 있는데 evidence 가 비었다. 근거 없는 확정 답변은 만들지 않는다."
            )

        # ★Team 은 승인 없이 실행하지 않는다 (CLAUDE.md §0.2)
        #   승인이 필요한 제안을 내면서 next_action 이 wait_for_approval 이 아니면 모순이다.
        if any(p.approval_required for p in self.action_proposals):
            if na is not NextAction.WAIT_FOR_APPROVAL:
                raise ValueError(
                    "approval_required=True 인 제안이 있는데 next_action 이 "
                    f"'{na.value}' 다. wait_for_approval 이어야 한다."
                )

        # 제안의 근거 id 는 이 결과의 evidence 안에 있어야 한다
        known = {e.evidence_id for e in self.evidence}
        for proposal in self.action_proposals:
            unknown = set(proposal.rationale_evidence_ids) - known
            if unknown:
                raise ValueError(
                    f"ActionProposal 이 이 결과에 없는 evidence 를 근거로 든다: {sorted(unknown)}"
                )
        return self


# ─────────────────────────────────────────────────────────────────────
# TeamManifest / TeamModule (계약 문서 §7, §8)
# ─────────────────────────────────────────────────────────────────────


class TeamManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str
    display_name: str
    contract_name: Literal["a_cop.team_task"]
    supported_contract_versions: list[str]
    capabilities: list[str] = Field(min_length=1)
    accepted_case_types: list[str]
    required_context: list[Literal["case_state", "policy", "db_facts", "history"]]
    allowed_tools: list[str]
    knowledge_scope: list[str]
    max_steps: int = Field(default=6, ge=1, le=12)
    active: bool = True
    implementation_revision: str


@runtime_checkable
class TeamModule(Protocol):
    """Core 가 Team 을 보는 유일한 창.

    ★Core 는 Team 내부(graph · prompt · retrieval)를 import 하지 않는다.
      tests/contract/test_core_isolation.py 가 import 검사로 강제한다.
    """

    manifest: TeamManifest

    async def execute(self, task: TeamTask) -> TeamResult: ...


# ─────────────────────────────────────────────────────────────────────
# Port (계약 문서 §9) — Phase 2 교체 지점
# ─────────────────────────────────────────────────────────────────────


@runtime_checkable
class MessageBrokerPort(Protocol):
    """MVP 구현체는 OutboxBrokerAdapter (outbox 테이블 + background worker).

    RedisStreamsAdapter 는 같은 Port 를 구현하는 Phase 2 대상이며 지금 본체를 만들지 않는다.
    """

    async def publish(self, topic: str, payload: dict, dedupe_key: str) -> str: ...
    async def ack(self, message_id: str) -> None: ...
