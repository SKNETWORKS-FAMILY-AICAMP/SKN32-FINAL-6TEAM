"""Case 가 가리키는 대상(`subject_ref`)을 **서버가 확인하는** 규격 — 코어는 대상의 이름을 모른다.

★`[결정 2026-09-17]` wiki `external/rest-endpoints.md` 「subject_ref」.
  클라이언트가 보낸 대상 id 를 믿지 않는다. 조립이 주입한 확인기가
  「이 테넌트·이 고객의 것인가」를 보고, 정규화한 참조와 라우팅 힌트를 돌려준다.

확인기 규격:

    resolver(conn, *, tenant_id, customer_id, subject_ref: dict) -> ResolvedSubject
    없거나 남의 것이면 SubjectNotFound — 응답은 404(있는지도 말하지 않는다)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class SubjectNotFound(LookupError):
    """대상이 없거나 이 고객의 것이 아니다."""


class SubjectUnsupported(RuntimeError):
    """이 조립에는 대상 확인기가 없다 — `subject_ref` 를 조용히 무시하지 않는다."""


@dataclass(frozen=True)
class ResolvedSubject:
    #: JSON 으로 저장할 수 있게 정규화한 참조(Team 이 `current_state.subject_ref` 로 받는다)
    subject_ref: dict[str, Any]
    #: 분류가 대상 접두를 못 붙였을 때만 쓰는 팀 고르기 힌트(`routing.case_type_of`)
    routing_hint: str | None = None
    #: ★힌트가 **클라이언트가 지정하고 서버가 확인한** 대상 부분에서 왔나. 참이면 분류보다 우선한다 —
    #:  확인된 사실이지 추측이 아니다. 거짓(짐작한 힌트)이면 분류에 접두가 없을 때만 쓴다.
    hint_is_verified: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


SubjectResolver = Callable[..., ResolvedSubject]

#: `[2026-09-17]` 대상이 정해진 고객 Case 의 문장 해석기 — **트랜잭션 밖**에서 분류 직전에 부른다.
#:  `interpreter(*, text, subject_ref) -> {"routing_hint": str | None, "report": dict | None}`
#:  돌려준 `routing_hint` 는 확인된 힌트로 기록돼 분류 접두보다 우선한다.
SubjectInterpreter = Callable[..., dict[str, Any]]

__all__ = ["ResolvedSubject", "SubjectInterpreter", "SubjectNotFound", "SubjectResolver", "SubjectUnsupported"]
