# -*- coding: utf-8 -*-
"""Team 이 **실제로 내는** 제안의 모든 필드가 검증 정책에 선언돼 있는가.

★이 검사가 없어서 두 번 새어나갔다(둘 다 커머스 시절).

    2026-08-17  `evidence`           — 실 브라우저 승인 클릭으로 발견
    2026-09-03  `calculation_basis`  — 코드를 읽다 발견

  둘 다 같은 구멍이다: 제안을 **만드는 쪽**과 승인 직전 **재검증하는 쪽**을
  이어서 보는 검사가 없었다. 각자의 단위 테스트는 다 초록이었다 —
  제안 생성 테스트는 제안이 나오는지만 봤고, 검증 테스트는 손으로 만든
  arguments 를 썼다. 그 사이에서 새는 것을 아무도 안 봤다.

★선언되지 않은 필드는 `verify_proposal` 이 "검사 규칙이 없으면 실행하지 않는다"
  로 막는다. 그 설계는 옳다 — 문제는 **막힌다는 사실을 아무도 몰랐다**는 것이다.
  환불 제안은 승인 자체가 되지 않는 상태였다.

★2026-09-10 여행으로 옮기며 **한 팀 고정에서 등록 전체 순회로 바꿨다.**
  전에는 `ReturnRefundTeam` 하나만 몰았다 — 나머지 팀이 새 필드를 실어도
  초록이었다. 지금은 `build_registry()` 가 주는 **등록된 모든 Team** 의
  제안 생성 capability 를 돌린다. 팀을 추가해도 이 검사가 따라온다.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import asyncio
import pytest

from app.composition import build_registry
from app.core.contracts import ContextPack, TeamTask
from app.modules.travel_ops.verification_policy import TRAVEL_OPS_POLICY

DECLARED = (set(TRAVEL_OPS_POLICY.references)
            | TRAVEL_OPS_POLICY.quantity_fields
            | TRAVEL_OPS_POLICY.opaque
            | TRAVEL_OPS_POLICY.ignored)

#: 가짜 도구가 돌려주는 값. ★Team 이 **제안을 만드는 데까지 가도록** 넉넉히 채운다.
#:  모자라면 Team 이 `_unknown` 으로 빠져 제안이 안 나오고, 그러면 이 검사가
#:  **아무것도 안 보면서 초록**이 된다 — 아래 `test_...actually_produced` 가 그걸 막는다.
_SOON = datetime.now(UTC) + timedelta(days=3)
_TOOL_VALUES: dict[str, Any] = {
    "read.booking": {"booking_id": "b-1", "booking_no": "BK-1", "kind": "activity",
                     "status": "confirmed", "starts_at": _SOON, "party_size": 2,
                     "capacity": 4, "amount_cents": 100_000, "locked": False},
    "read.policy": [{"cancel_deadline_hours": 48, "penalty_rate": 0.2,
                     "change_deadline_hours": 24}],
    "read.place": {"place_id": "p-1", "name": "장소", "weather_sensitive": False,
                   "confirmed_at": _SOON, "open_at_slot": True,
                   "dietary": [], "dietary_absent": []},
    "read.weather": {"condition": "clear", "risk": "low"},
    "read.route": {"route_id": "r-1", "duration_minutes": 30, "gap_minutes": 60},
    "read.transit": {"last_departure_ok": True},
    "read.supplier": {"supplier": "S", "supplier_ref": "SR-1", "status": "confirmed",
                      "starts_at": _SOON, "party_size": 2},
}


class FakeTools:
    """★`budget` 을 받는다 — 여행 `_base._read` 가 항상 넘긴다.
    빠뜨리면 TypeError 가 나고 그건 팀 결함이 아니라 이 가짜의 결함이다."""

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        seen.add(f"{name}:{sorted((arguments or {}).items(), key=str)}")
        return _TOOL_VALUES.get(name)


def _task(team_id: str, capability: str, manifest) -> TeamTask:
    case_id = uuid4()
    context = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id=team_id, tenant_id="tenant",
        knowledge_scope=manifest.knowledge_scope,
        current_state={"customer_id": str(uuid4()), "request_id": str(uuid4())},
        estimated_input_tokens=10,
    )
    return TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id=team_id,
        capability=capability, case_version=1,
        input_text="일정을 바꾸고 싶습니다", context=context,
        allowed_tools=manifest.allowed_tools,
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )


def _cases() -> list[tuple[str, str]]:
    return [(m.team_id, capability)
            for m in build_registry().manifests()
            for capability in m.capabilities]


CASES = _cases()


def _run(team_id: str, capability: str):
    entry = build_registry(tools=FakeTools(), llm=object()).get(team_id)
    task = _task(team_id, capability, entry.manifest)
    return asyncio.run(entry.module.execute(task))


def test_there_is_something_to_drive():
    """★목록이 비면 아래 검사가 전부 통과한다."""
    assert CASES, "등록된 Team 의 capability 가 하나도 없다."


@pytest.mark.parametrize("team_id,capability", CASES, ids=lambda v: v)
def test_every_proposal_field_is_declared(team_id: str, capability: str):
    result = _run(team_id, capability)
    for proposal in result.action_proposals or ():
        undeclared = sorted(set(proposal.arguments) - DECLARED)
        assert not undeclared, (
            f"{team_id}.{capability} 의 '{proposal.action_type}' 제안이 검증 정책에 "
            f"없는 필드를 싣는다: {undeclared}\n"
            f"  → `app/modules/travel_ops/verification_policy.py` 에 넣는다. "
            f"대조 가능하면 references/quantities, 설명값이면 ignored, "
            f"대조 수단이 없으면 opaque.\n"
            f"  ★넣지 않으면 승인 직전 재검증이 **이 제안을 통째로 막는다.**")


def test_at_least_one_proposal_was_actually_produced():
    """★위 검사는 제안이 0개면 전부 통과한다. 하나는 실제로 나와야 한다.

    나오지 않는다면 가짜 도구 값이 모자라 Team 이 `_unknown` 으로 빠진 것이다 —
    그때는 이 파일이 **아무것도 검사하지 않으면서 초록**이다.
    """
    produced = [(team_id, capability, p.action_type)
                for team_id, capability in CASES
                for p in (_run(team_id, capability).action_proposals or ())]
    assert produced, (
        "등록된 어느 Team 도 제안을 만들지 않았다. `_TOOL_VALUES` 가 Team 이 "
        "제안까지 가는 데 필요한 값을 다 갖고 있는지 확인한다.")
    print("제안을 낸 조합:", produced)
