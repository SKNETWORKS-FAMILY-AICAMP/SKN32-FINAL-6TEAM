"""전이표가 현재 wiki의 명시적 상태 계약과 일치하는지 대조한다.

★이 테스트가 있는 이유: 코드의 전이표는 조용히 늘어난다.
  "이 전이도 필요하겠지" 하고 하나 추가하면 상태 기계가 계획서와 어긋나는데
  기존 테스트는 전부 통과한다. 그래서 **표 자체를 검사**한다.

정본: wiki/runtime/case-lifecycle.md "허용 전이"와 2026-10-11 재개 중 담당 변경 계약.
v5의 최초 상태표는 기록으로 보존하며 현재 wiki의 명시적 후속 결정을 우선한다.
"""

from __future__ import annotations

import pytest

from app.core.contracts import CaseStatus, InvalidTransition
from app.core.case_lifecycle.case import CaseProjection, apply_event
from app.core.case_lifecycle.events import (
    REQUIRED_PAYLOAD_KEYS,
    TERMINAL_STATUSES,
    TRANSITIONS,
    EventType,
    allowed_next_statuses,
)

#: 현재 wiki의 허용 전이 표를 별도로 적은 기대값이다.
#: ★실행 코드에서 계산하지 않는다. resuming의 routed 자기전이만 후속 계약으로 추가됐다.
WIKI_ALLOWED_NEXT: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.NEW: {CaseStatus.CLASSIFYING, CaseStatus.CANCELLED},
    CaseStatus.CLASSIFYING: {CaseStatus.ROUTING, CaseStatus.ESCALATED},
    CaseStatus.ROUTING: {CaseStatus.RUNNING, CaseStatus.ESCALATED},
    CaseStatus.RUNNING: {
        CaseStatus.WAITING_INPUT,
        CaseStatus.WAITING_APPROVAL,
        CaseStatus.WAITING_EXTERNAL,
        CaseStatus.RESOLVED,
        CaseStatus.FAILED,
        CaseStatus.ESCALATED,
    },
    CaseStatus.WAITING_INPUT: {CaseStatus.RESUMING, CaseStatus.ESCALATED},
    CaseStatus.WAITING_APPROVAL: {CaseStatus.RESUMING, CaseStatus.ESCALATED},
    CaseStatus.WAITING_EXTERNAL: {CaseStatus.RESUMING, CaseStatus.ESCALATED},
    CaseStatus.RESUMING: {CaseStatus.RESUMING, CaseStatus.RUNNING, CaseStatus.ESCALATED},
    CaseStatus.RESOLVED: {CaseStatus.CANCELLED},
    CaseStatus.ESCALATED: {CaseStatus.CANCELLED},
    CaseStatus.FAILED: {CaseStatus.ESCALATED},
    CaseStatus.CANCELLED: set(),
}


# invariant: INV-CS-RT-014
@pytest.mark.parametrize("status", list(CaseStatus))
def test_allowed_next_statuses_match_v5(status: CaseStatus) -> None:
    # 기존 불변식 카탈로그의 시험 식별자는 유지하고 대조 정본만 현재 wiki로 갱신한다.
    assert set(allowed_next_statuses(status)) == WIKI_ALLOWED_NEXT[status], (
        f"{status.value} 의 허용 다음 상태가 wiki/runtime/case-lifecycle.md 와 다르다"
    )


def test_only_routed_can_keep_the_same_state_while_resuming() -> None:
    same_state = {key: target for key, target in TRANSITIONS.items() if key[0] is target}
    assert same_state == {(CaseStatus.RESUMING, EventType.ROUTED): CaseStatus.RESUMING}


def test_resume_routing_changes_owner_but_preserves_reply_token_and_wait_reason() -> None:
    before = CaseProjection(status=CaseStatus.RESUMING, version=8, owner_team_id="dining",
                            state_json={"customer_input": "활동 일정이요", "resume_token_used": True,
                                        "wait_reason": "customer_input"})
    routed = apply_event(before, EventType.ROUTED,
                         {"owner_team_id": "activity", "capability": "activity.change",
                          "state_patch": {"subject_ref": {"kind": "trip", "request": {"action": "apply_change"}}}})
    assert routed.status is CaseStatus.RESUMING and routed.version == 9
    assert routed.owner_team_id == "activity"
    assert all(routed.state_json[key] == value for key, value in before.state_json.items())
    running = apply_event(routed, EventType.RESUMED, {"resume_node": "validate_input"})
    assert running.status is CaseStatus.RUNNING and running.version == 10


@pytest.mark.parametrize("event,payload", [
    (EventType.VALID_INPUT, {"resume_token_hash": "already-consumed"}),
    (EventType.COMPLETED, {"answer_ref": "premature-result"}),
])
def test_resuming_cannot_consume_input_again_or_complete_before_resumed(event, payload) -> None:
    with pytest.raises(InvalidTransition, match="허용되지 않은 전이"):
        apply_event(CaseProjection(status=CaseStatus.RESUMING, version=8), event, payload)


# invariant: INV-CS-RT-012
def test_all_twelve_statuses_exist() -> None:
    """v5 §5-1 은 정확히 12개 상태를 정의한다."""
    assert len(CaseStatus) == 12


# invariant: INV-CS-RT-013
def test_cancelled_is_terminal() -> None:
    assert CaseStatus.CANCELLED in TERMINAL_STATUSES
    assert allowed_next_statuses(CaseStatus.CANCELLED) == ()


def test_every_event_has_payload_schema() -> None:
    """payload schema 가 없는 이벤트는 검증을 통과해 버린다 — 조용한 구멍이다."""
    missing = [e.value for e in EventType if e not in REQUIRED_PAYLOAD_KEYS]
    assert not missing, f"payload schema 미등록 이벤트: {missing}"


# invariant: INV-CS-RT-016
def test_every_event_is_used_in_transition_table() -> None:
    """쓰이지 않는 이벤트는 죽은 코드다(RULE.md §3.3)."""
    used = {event for _status, event in TRANSITIONS}
    unused = [e.value for e in EventType if e not in used]
    assert not unused, f"전이표에 없는 이벤트: {unused}"


# invariant: INV-CS-RT-017
def test_classification_failure_escalates_not_silently_continues() -> None:
    """★v5 §2 — 분류 실패는 조용히 넘어가지 않는다."""
    assert TRANSITIONS[(CaseStatus.CLASSIFYING, EventType.CLASSIFICATION_FAILED)] is (
        CaseStatus.ESCALATED
    )


# invariant: INV-CS-RT-018
def test_wait_expiry_escalates_not_auto_resolves() -> None:
    """★v5 §5-4 — TTL 만료는 자동 종료가 아니라 escalated 다."""
    for waiting in (
        CaseStatus.WAITING_INPUT,
        CaseStatus.WAITING_APPROVAL,
        CaseStatus.WAITING_EXTERNAL,
    ):
        assert TRANSITIONS[(waiting, EventType.WAIT_EXPIRED)] is CaseStatus.ESCALATED


# invariant: INV-CS-RT-019
def test_rejection_does_not_resume() -> None:
    """승인 거절이 실행 경로로 돌아가면 안 된다."""
    assert TRANSITIONS[(CaseStatus.WAITING_APPROVAL, EventType.REJECTED)] is CaseStatus.ESCALATED
