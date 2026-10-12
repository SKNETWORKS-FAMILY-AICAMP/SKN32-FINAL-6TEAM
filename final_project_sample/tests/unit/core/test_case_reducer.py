"""Case projection 리듀서 — DB 없이 도는 순수 테스트.

★replay 동치성(DoD 3)은 여기서 먼저 증명한다.
  `transition_case()` 와 `replay_case()` 가 같은 리듀서를 쓰므로,
  리듀서가 결정적이면 재생 결과도 반드시 일치한다.
"""

from __future__ import annotations

import pytest

from acop_basement.core.contracts import CaseStatus, InvalidTransition
from acop_basement.domain.case import CaseProjection, apply_event, fold_events, validate_payload
from acop_basement.domain.events import EventType

CREATED_PAYLOAD = {"channel": "personal_ai", "message": "해지했는데 결제가 됐어요"}
CLASSIFIED_PAYLOAD = {
    "intent": "billing",
    "issue_code": "post_cancel_charge",
    "sentiment": "negative",
}
ROUTED_PAYLOAD = {"owner_team_id": "demo_team", "capability": "demo.investigate"}


def new_case() -> CaseProjection:
    return CaseProjection(status=CaseStatus.NEW, version=0)


# ── 기본 전이 ─────────────────────────────────────────────────────────


def test_created_moves_to_classifying_and_bumps_version() -> None:
    case = apply_event(new_case(), EventType.CREATED, CREATED_PAYLOAD)
    assert case.status is CaseStatus.CLASSIFYING
    assert case.version == 1


def test_happy_path_to_running() -> None:
    case = new_case()
    case = apply_event(case, EventType.CREATED, CREATED_PAYLOAD)
    case = apply_event(case, EventType.CLASSIFIED, CLASSIFIED_PAYLOAD)
    case = apply_event(case, EventType.ROUTED, ROUTED_PAYLOAD)
    assert case.status is CaseStatus.RUNNING
    assert case.version == 3
    assert case.intent == "billing"
    assert case.issue_code == "post_cancel_charge"
    assert case.sentiment == "negative"
    assert case.owner_team_id == "demo_team"


def test_illegal_transition_is_rejected() -> None:
    """new 에서 곧장 resolved 로 갈 수 없다."""
    with pytest.raises(InvalidTransition, match="허용되지 않은 전이"):
        apply_event(new_case(), EventType.COMPLETED, {"answer_ref": "x"})


def test_cancelled_is_terminal() -> None:
    case = apply_event(new_case(), EventType.CANCELLED_BY_USER, {})
    assert case.status is CaseStatus.CANCELLED
    with pytest.raises(InvalidTransition):
        apply_event(case, EventType.CREATED, CREATED_PAYLOAD)


# ── payload schema (v5 §5-3) ─────────────────────────────────────────


def test_missing_payload_key_is_rejected() -> None:
    with pytest.raises(InvalidTransition, match="필수 키가 없다"):
        validate_payload(EventType.CLASSIFIED, {"intent": "billing"})


def test_classified_requires_all_three_labels() -> None:
    """★감성·의도·이슈 셋 다 있어야 한다 (v5 §2 인라인 분류)."""
    partial = {"intent": "billing", "issue_code": "x"}
    with pytest.raises(InvalidTransition):
        apply_event(
            apply_event(new_case(), EventType.CREATED, CREATED_PAYLOAD),
            EventType.CLASSIFIED,
            partial,
        )


# ── 분류 실패 시 라벨을 채우지 않는다 (CLAUDE.md §1) ──────────────────


def test_classification_failure_leaves_labels_empty() -> None:
    case = apply_event(new_case(), EventType.CREATED, CREATED_PAYLOAD)
    case = apply_event(
        case, EventType.CLASSIFICATION_FAILED, {"failure_code": "llm_timeout"}
    )
    assert case.status is CaseStatus.ESCALATED
    assert case.intent is None
    assert case.issue_code is None
    assert case.sentiment is None


# ── state_json 병합 ───────────────────────────────────────────────────


def test_state_patch_merges_and_does_not_wipe() -> None:
    case = apply_event(
        new_case(), EventType.CREATED, {**CREATED_PAYLOAD, "state_patch": {"a": 1}}
    )
    case = apply_event(
        case, EventType.CLASSIFIED, {**CLASSIFIED_PAYLOAD, "state_patch": {"b": 2}}
    )
    assert case.state_json["a"] == 1
    assert case.state_json["b"] == 2
    assert case.state_json["last_event"] == "classified"


# ── replay 동치성 (DoD 3) ─────────────────────────────────────────────


WAIT_APPROVAL_SEQUENCE = [
    (EventType.CREATED, CREATED_PAYLOAD),
    (EventType.CLASSIFIED, CLASSIFIED_PAYLOAD),
    (EventType.ROUTED, ROUTED_PAYLOAD),
    (EventType.APPROVAL_REQUIRED, {"action_id": "a_01"}),
    (EventType.APPROVED, {"action_id": "a_01", "approver_id": "op_01"}),
    (EventType.RESUMED, {"resume_node": "execute_approved_action"}),
    (EventType.COMPLETED, {"answer_ref": "ans_01"}),
]


def test_fold_reproduces_step_by_step_result() -> None:
    """이벤트를 하나씩 적용한 결과와 통째로 접은 결과가 같다."""
    stepwise = new_case()
    for event_type, payload in WAIT_APPROVAL_SEQUENCE:
        stepwise = apply_event(stepwise, event_type, payload)

    replayed = fold_events(WAIT_APPROVAL_SEQUENCE)
    assert replayed == stepwise
    assert replayed.status is CaseStatus.RESOLVED
    assert replayed.version == len(WAIT_APPROVAL_SEQUENCE)


def test_replay_is_deterministic() -> None:
    assert fold_events(WAIT_APPROVAL_SEQUENCE) == fold_events(WAIT_APPROVAL_SEQUENCE)


def test_version_always_equals_event_count() -> None:
    """version 은 이벤트 수와 같다 — case_events.aggregate_version 과 맞물린다."""
    for i in range(1, len(WAIT_APPROVAL_SEQUENCE) + 1):
        assert fold_events(WAIT_APPROVAL_SEQUENCE[:i]).version == i


# ── 승인 거절 / TTL 경로 ──────────────────────────────────────────────


def test_rejected_approval_escalates() -> None:
    case = fold_events(WAIT_APPROVAL_SEQUENCE[:4])
    assert case.status is CaseStatus.WAITING_APPROVAL
    case = apply_event(case, EventType.REJECTED, {"action_id": "a_01", "approver_id": "op_01"})
    assert case.status is CaseStatus.ESCALATED


def test_wait_expiry_escalates() -> None:
    case = fold_events(WAIT_APPROVAL_SEQUENCE[:4])
    case = apply_event(case, EventType.WAIT_EXPIRED, {"wait_reason": "human_approval"})
    assert case.status is CaseStatus.ESCALATED
