"""전이표가 v5 §5-1 상태 정의표와 일치하는지 대조한다.

★이 테스트가 있는 이유: 코드의 전이표는 조용히 늘어난다.
  "이 전이도 필요하겠지" 하고 하나 추가하면 상태 기계가 계획서와 어긋나는데
  기존 테스트는 전부 통과한다. 그래서 **표 자체를 검사**한다.

기준선: ../A-COP_구현계획서_v5.md §5-1 "허용 다음 상태" 열
"""

from __future__ import annotations

import pytest

from acop_basement.core.contracts import CaseStatus
from acop_basement.domain.events import (
    REQUIRED_PAYLOAD_KEYS,
    TERMINAL_STATUSES,
    TRANSITIONS,
    EventType,
    allowed_next_statuses,
)

#: v5 §5-1 의 "허용 다음 상태" 열을 그대로 옮긴 것.
#: ★코드에서 가져오지 않는다 — 계획서를 보고 손으로 옮겨야 대조가 성립한다.
V5_ALLOWED_NEXT: dict[CaseStatus, set[CaseStatus]] = {
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
    CaseStatus.RESUMING: {CaseStatus.RUNNING, CaseStatus.ESCALATED},
    CaseStatus.RESOLVED: {CaseStatus.CANCELLED},
    CaseStatus.ESCALATED: {CaseStatus.CANCELLED},
    CaseStatus.FAILED: {CaseStatus.ESCALATED},
    CaseStatus.CANCELLED: set(),
}


@pytest.mark.parametrize("status", list(CaseStatus))
def test_allowed_next_statuses_match_v5(status: CaseStatus) -> None:
    assert set(allowed_next_statuses(status)) == V5_ALLOWED_NEXT[status], (
        f"{status.value} 의 허용 다음 상태가 v5 §5-1 과 다르다"
    )


def test_all_twelve_statuses_exist() -> None:
    """v5 §5-1 은 정확히 12개 상태를 정의한다."""
    assert len(CaseStatus) == 12


def test_cancelled_is_terminal() -> None:
    assert CaseStatus.CANCELLED in TERMINAL_STATUSES
    assert allowed_next_statuses(CaseStatus.CANCELLED) == ()


def test_every_event_has_payload_schema() -> None:
    """payload schema 가 없는 이벤트는 검증을 통과해 버린다 — 조용한 구멍이다."""
    missing = [e.value for e in EventType if e not in REQUIRED_PAYLOAD_KEYS]
    assert not missing, f"payload schema 미등록 이벤트: {missing}"


def test_every_event_is_used_in_transition_table() -> None:
    """쓰이지 않는 이벤트는 죽은 코드다(RULE.md §3.3)."""
    used = {event for _status, event in TRANSITIONS}
    unused = [e.value for e in EventType if e not in used]
    assert not unused, f"전이표에 없는 이벤트: {unused}"


def test_classification_failure_escalates_not_silently_continues() -> None:
    """★v5 §2 — 분류 실패는 조용히 넘어가지 않는다."""
    assert TRANSITIONS[(CaseStatus.CLASSIFYING, EventType.CLASSIFICATION_FAILED)] is (
        CaseStatus.ESCALATED
    )


def test_wait_expiry_escalates_not_auto_resolves() -> None:
    """★v5 §5-4 — TTL 만료는 자동 종료가 아니라 escalated 다."""
    for waiting in (
        CaseStatus.WAITING_INPUT,
        CaseStatus.WAITING_APPROVAL,
        CaseStatus.WAITING_EXTERNAL,
    ):
        assert TRANSITIONS[(waiting, EventType.WAIT_EXPIRED)] is CaseStatus.ESCALATED


def test_rejection_does_not_resume() -> None:
    """승인 거절이 실행 경로로 돌아가면 안 된다."""
    assert TRANSITIONS[(CaseStatus.WAITING_APPROVAL, EventType.REJECTED)] is CaseStatus.ESCALATED
