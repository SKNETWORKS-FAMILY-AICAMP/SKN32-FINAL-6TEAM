"""Case 이벤트와 허용 상태 전이표.

★이 표가 v5 §5-1(상태 정의표)·§5-2(전이도)의 **코드 상 유일한 대응물**이다.
  전이 규칙을 다른 곳에 다시 쓰지 않는다. 여기 없는 전이는 일어날 수 없다.

상태 변경은 `app/core/transition.py:transition_case()` 만이 진입점이다(CLAUDE.md §0.3).
"""

from __future__ import annotations

from enum import Enum

from acop_basement.core.contracts import CaseStatus


class EventType(str, Enum):
    """Case 상태를 움직이는 이벤트. v5 §5-2 의 전이 라벨과 1:1."""

    CREATED = "created"
    CANCELLED_BY_USER = "cancelled_by_user"

    CLASSIFIED = "classified"
    CLASSIFICATION_FAILED = "classification_failed"

    ROUTED = "routed"
    ROUTING_FAILED = "routing_failed"

    MISSING_INPUT = "missing_input"
    APPROVAL_REQUIRED = "approval_required"
    ASYNC_PROVIDER = "async_provider"
    COMPLETED = "completed"
    RETRY_EXHAUSTED = "retry_exhausted"
    GUARDRAIL_ESCALATED = "guardrail_escalated"

    VALID_INPUT = "valid_input"
    APPROVED = "approved"
    REJECTED = "rejected"
    VALID_CALLBACK = "valid_callback"
    WAIT_EXPIRED = "wait_expired"

    RESUMED = "resumed"
    RESUME_FAILED = "resume_failed"

    FAILURE_ESCALATED = "failure_escalated"


#: (현재 상태, 이벤트) -> 다음 상태.
#: v5 §5-1 의 "허용 다음 상태" 열과 §5-2 의 전이 라벨을 합친 것이다.
#: ★여기 없는 조합은 InvalidTransition 이다. 예외를 만들지 않는다.
TRANSITIONS: dict[tuple[CaseStatus, EventType], CaseStatus] = {
    # new
    (CaseStatus.NEW, EventType.CREATED): CaseStatus.CLASSIFYING,
    (CaseStatus.NEW, EventType.CANCELLED_BY_USER): CaseStatus.CANCELLED,
    # classifying — ★분류 실패는 조용히 넘어가지 않는다 (v5 §2, CLAUDE.md §1)
    (CaseStatus.CLASSIFYING, EventType.CLASSIFIED): CaseStatus.ROUTING,
    (CaseStatus.CLASSIFYING, EventType.CLASSIFICATION_FAILED): CaseStatus.ESCALATED,
    # routing
    (CaseStatus.ROUTING, EventType.ROUTED): CaseStatus.RUNNING,
    (CaseStatus.ROUTING, EventType.ROUTING_FAILED): CaseStatus.ESCALATED,
    # running
    (CaseStatus.RUNNING, EventType.MISSING_INPUT): CaseStatus.WAITING_INPUT,
    (CaseStatus.RUNNING, EventType.APPROVAL_REQUIRED): CaseStatus.WAITING_APPROVAL,
    (CaseStatus.RUNNING, EventType.ASYNC_PROVIDER): CaseStatus.WAITING_EXTERNAL,
    (CaseStatus.RUNNING, EventType.COMPLETED): CaseStatus.RESOLVED,
    (CaseStatus.RUNNING, EventType.RETRY_EXHAUSTED): CaseStatus.FAILED,
    (CaseStatus.RUNNING, EventType.GUARDRAIL_ESCALATED): CaseStatus.ESCALATED,
    # waiting_input
    (CaseStatus.WAITING_INPUT, EventType.VALID_INPUT): CaseStatus.RESUMING,
    (CaseStatus.WAITING_INPUT, EventType.WAIT_EXPIRED): CaseStatus.ESCALATED,
    # waiting_approval — 거절도 TTL 도 자동 종료가 아니라 escalated 다 (v5 §5-2)
    (CaseStatus.WAITING_APPROVAL, EventType.APPROVED): CaseStatus.RESUMING,
    (CaseStatus.WAITING_APPROVAL, EventType.REJECTED): CaseStatus.ESCALATED,
    (CaseStatus.WAITING_APPROVAL, EventType.WAIT_EXPIRED): CaseStatus.ESCALATED,
    # ★v7 §9-E — 승인 직전 재검증이 실패하면 여기서 escalated 로 간다.
    #   승인을 기다리는 동안에도 사실은 바뀐다(환불 가능 잔액 등). 그때 가드레일이 걸린다.
    #   ★상태기계가 이 전이가 없다고 거부해서 알았다 — 재검증 코드를 먼저 쓰고
    #     전이표를 안 열어 본 탓이다. 기계가 설계 구멍을 먼저 잡았다.
    (CaseStatus.WAITING_APPROVAL, EventType.GUARDRAIL_ESCALATED): CaseStatus.ESCALATED,
    # waiting_external
    (CaseStatus.WAITING_EXTERNAL, EventType.VALID_CALLBACK): CaseStatus.RESUMING,
    (CaseStatus.WAITING_EXTERNAL, EventType.WAIT_EXPIRED): CaseStatus.ESCALATED,
    # resuming
    (CaseStatus.RESUMING, EventType.RESUMED): CaseStatus.RUNNING,
    (CaseStatus.RESUMING, EventType.RESUME_FAILED): CaseStatus.ESCALATED,
    # 종료 계열
    (CaseStatus.FAILED, EventType.FAILURE_ESCALATED): CaseStatus.ESCALATED,
    (CaseStatus.RESOLVED, EventType.CANCELLED_BY_USER): CaseStatus.CANCELLED,
    (CaseStatus.ESCALATED, EventType.CANCELLED_BY_USER): CaseStatus.CANCELLED,
}

#: 더 이상 나갈 곳이 없는 상태. v5 §5-1 "cancelled → 없음".
TERMINAL_STATUSES: frozenset[CaseStatus] = frozenset({CaseStatus.CANCELLED})

#: 이벤트별 payload 필수 키. ★없는 키를 조용히 넘기지 않는다(v5 §5-3 payload schema 검증).
REQUIRED_PAYLOAD_KEYS: dict[EventType, tuple[str, ...]] = {
    EventType.CREATED: ("channel", "message"),
    EventType.CLASSIFIED: ("intent", "issue_code", "sentiment"),
    EventType.CLASSIFICATION_FAILED: ("failure_code",),
    EventType.ROUTED: ("owner_team_id", "capability"),
    EventType.ROUTING_FAILED: ("failure_code",),
    EventType.MISSING_INPUT: ("required_input_schema",),
    EventType.APPROVAL_REQUIRED: ("action_id",),
    EventType.ASYNC_PROVIDER: ("provider_ref",),
    EventType.COMPLETED: ("answer_ref",),
    EventType.RETRY_EXHAUSTED: ("failure_code",),
    EventType.GUARDRAIL_ESCALATED: ("guardrail", "observed"),
    EventType.VALID_INPUT: ("resume_token_hash",),
    EventType.APPROVED: ("action_id", "approver_id"),
    EventType.REJECTED: ("action_id", "approver_id"),
    EventType.VALID_CALLBACK: ("provider_ref",),
    EventType.WAIT_EXPIRED: ("wait_reason",),
    EventType.RESUMED: ("resume_node",),
    EventType.RESUME_FAILED: ("failure_code",),
    EventType.FAILURE_ESCALATED: ("failure_code",),
    EventType.CANCELLED_BY_USER: (),
}


def next_status(current: CaseStatus, event: EventType) -> CaseStatus | None:
    """허용된 전이면 다음 상태를, 아니면 None 을 돌려준다."""
    return TRANSITIONS.get((current, event))


def allowed_events(current: CaseStatus) -> tuple[EventType, ...]:
    """현재 상태에서 낼 수 있는 이벤트 (오류 메시지용)."""
    return tuple(evt for (status, evt) in TRANSITIONS if status is current)


def allowed_next_statuses(current: CaseStatus) -> tuple[CaseStatus, ...]:
    """v5 §5-1 '허용 다음 상태' 열과 대조하기 위한 조회."""
    seen: list[CaseStatus] = []
    for (status, _evt), nxt in TRANSITIONS.items():
        if status is current and nxt not in seen:
            seen.append(nxt)
    return tuple(seen)
