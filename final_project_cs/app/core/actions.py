"""승인 없이 적용되는 제안의 **적용기 규격** — 코어는 무엇을 바꾸는지 모른다.

★왜 있나(`[결정 2026-09-17]`, wiki `actions/approval.md` 「승인 없이 적용되는 제안」).
  v11 §4-C 는 「먼저 고치고 알린다」를 **우리 DB 안의 대상**에만 허락한다. 전에는
  Team 이 `respond` 와 함께 낸 제안이 저장도 실행도 안 되고 사라졌다
  (`controller.py` `_event_for_result` 의 `RESPOND` 갈래가 제안을 보지 않았다).

★basement 다. 여기에는 **대상의 이름이 없다.** 적용기는 도메인 모듈이 만들어
  조립이 넣는다 — 코어가 아는 것은 이 규격뿐이다.

규격:

    action_type   이 적용기가 맡는 제안 종류
    auto_apply    True 여야 승인 없이 적용한다. False 면 코어가 escalated 로 보낸다
    subject(args) 멱등 키의 대상 id — **서버가 인자에서 꺼낸다**(v11 §4-E). 못 꺼내면 ActionRejected
    apply(conn, …) 같은 트랜잭션 안에서 적용하고 AppliedAction 을 돌려준다
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from uuid import UUID

from app.core.transition import OutboxMessage


class ActionRejected(RuntimeError):
    """대상이 없거나, 이 고객의 것이 아니거나, 인자가 적용할 수 없는 모양이다."""


class ActionConflict(RuntimeError):
    """제안을 계산한 뒤 대상이 바뀌었다 — 재계산 없이 다시 밀어 넣지 않는다."""


@dataclass(frozen=True)
class AppliedAction:
    """적용 결과. ★`outbox` 는 코어가 Case 전이와 **같은 트랜잭션**에 싣는다."""

    result_ref: str
    summary: dict[str, Any] = field(default_factory=dict)
    outbox: list[OutboxMessage] = field(default_factory=list)


class ActionHandler(Protocol):
    action_type: str
    auto_apply: bool

    def subject(self, arguments: Mapping[str, Any]) -> str: ...

    def apply(self, conn: Any, *, tenant_id: str, customer_id: UUID, case_id: UUID,
              arguments: Mapping[str, Any]) -> AppliedAction: ...


class ActionHandlers:
    """`action_type` → 적용기. 같은 종류를 두 번 등록하면 조립 오류다."""

    def __init__(self, handlers: list[ActionHandler] | tuple[ActionHandler, ...] = ()) -> None:
        self._by_type: dict[str, ActionHandler] = {}
        for handler in handlers:
            if handler.action_type in self._by_type:
                raise ValueError(f"duplicate action handler: {handler.action_type}")
            self._by_type[handler.action_type] = handler

    def get(self, action_type: str) -> ActionHandler | None:
        return self._by_type.get(action_type)

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_type))


__all__ = ["ActionConflict", "ActionHandler", "ActionHandlers", "ActionRejected", "AppliedAction"]
