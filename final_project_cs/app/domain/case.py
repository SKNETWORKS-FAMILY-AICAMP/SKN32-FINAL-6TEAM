"""Case projection 리듀서 — 이벤트를 상태로 접는 순수 함수.

★`transition_case()` 와 `replay_case()` 가 **같은 이 함수**를 쓴다.
  그래서 projection 을 지우고 event 를 재생하면 반드시 같은 상태가 나온다(v5 §6-2, DoD 3).
  둘이 각자 계산하면 조용히 어긋난다.

여기에는 DB 도 I/O 도 없다. 순수하게 유지한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from app.core.contracts import CaseStatus, InvalidTransition
from app.domain.events import (
    REQUIRED_PAYLOAD_KEYS,
    EventType,
    allowed_events,
    next_status,
)


@dataclass(frozen=True)
class CaseProjection:
    """`customer_cases` 한 행에 대응하는 값 객체."""

    status: CaseStatus
    version: int
    state_json: dict[str, Any] = field(default_factory=dict)
    intent: str | None = None
    issue_code: str | None = None
    sentiment: str | None = None
    owner_team_id: str | None = None


def validate_payload(event_type: EventType, payload: dict[str, Any]) -> None:
    """이벤트별 필수 키를 검사한다. ★없는 키를 조용히 넘기지 않는다(v5 §5-3)."""
    required = REQUIRED_PAYLOAD_KEYS.get(event_type)
    if required is None:
        raise InvalidTransition(f"payload schema 가 등록되지 않은 이벤트다: {event_type.value}")
    missing = [key for key in required if key not in payload]
    if missing:
        raise InvalidTransition(
            f"'{event_type.value}' payload 에 필수 키가 없다: {missing} (필요: {list(required)})"
        )


def apply_event(
    current: CaseProjection,
    event_type: EventType,
    payload: dict[str, Any],
) -> CaseProjection:
    """이벤트 하나를 projection 에 적용한다.

    허용되지 않은 전이거나 payload 가 모자라면 `InvalidTransition` 을 던진다.
    version 은 여기서 +1 한다 — 이벤트의 `aggregate_version` 과 같은 값이 된다.
    """
    validate_payload(event_type, payload)

    nxt = next_status(current.status, event_type)
    if nxt is None:
        raise InvalidTransition(
            f"허용되지 않은 전이: {current.status.value} --{event_type.value}--> ? "
            f"(이 상태에서 가능한 이벤트: {[e.value for e in allowed_events(current.status)]})"
        )

    # state_json 은 덮어쓰기가 아니라 병합이다. 이전 근거를 지우지 않는다.
    state = dict(current.state_json)
    if isinstance(payload.get("state_patch"), dict):
        state.update(payload["state_patch"])
    state["last_event"] = event_type.value

    updates: dict[str, Any] = {
        "status": nxt,
        "version": current.version + 1,
        "state_json": state,
    }

    # 분류 결과는 CLASSIFIED 에서만 채워진다.
    # ★실패하면 채우지 않는다 — 모르면 비워 둔다(CLAUDE.md §1).
    if event_type is EventType.CLASSIFIED:
        updates["intent"] = payload["intent"]
        updates["issue_code"] = payload["issue_code"]
        updates["sentiment"] = payload["sentiment"]
    elif event_type is EventType.ROUTED:
        updates["owner_team_id"] = payload["owner_team_id"]

    return replace(current, **updates)


def fold_events(events: list[tuple[EventType, dict[str, Any]]]) -> CaseProjection:
    """이벤트 열을 처음부터 접어 projection 을 재생한다 (replay).

    Case 는 항상 `new` / version 0 에서 시작한다.
    """
    projection = CaseProjection(status=CaseStatus.NEW, version=0)
    for event_type, payload in events:
        projection = apply_event(projection, event_type, payload)
    return projection
