# -*- coding: utf-8 -*-
"""Booking Handoff Team — 바꿔야 할 것을 정리해 **넘긴다**.

★이름이 `Execution` 이 아니라 `Handoff` 인 것이 핵심이다(v10 §5).
  기본 동작은 **인계**다 — 무엇을 어떻게 바꿔야 하는지 정리해서 넘긴다.
  실제로 업체 예약을 바꾸는 것은 **시연 모드(Mock 공급자) 한정**이고,
  그때도 `ActionProposal` 로 승인 대기에 올린다.

★Team 은 side effect 를 실행하지 않는다. 이 팀도 예외가 아니다.
"""
from __future__ import annotations

from app.core.contracts import NextAction, TeamManifest, TeamResult, TeamTask

from ._base import TravelTeamBase


class BookingHandoffTeam(TravelTeamBase):
    manifest = TeamManifest(
        team_id="booking_handoff",
        display_name="Booking Handoff Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=[
            "booking.verify",          # 예약이 실재하고 우리가 아는 것과 같은가
            "booking.prepare_change",  # 변경에 필요한 것을 정리한다
            "booking.prepare_cancel",  # 취소에 필요한 것을 정리한다
        ],
        accepted_case_types=["booking"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.booking", "read.policy", "read.supplier"],
        knowledge_scope=["booking", "cancellation", "penalty", "supplier"],
        max_steps=6,
        active=True,
        implementation_revision="2026-09-09",
        default_capability="booking.verify",
    )

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked

        seen: set[str] = set()
        booking = self._read(task, "read.booking", {"case_id": str(task.case_id)}, seen)
        evidence = self._evidence(task, source_id="read.booking",
                                  claim="예약 내역", value=booking)
        if booking is None:
            return self._unknown(task, "예약 내역", evidence)

        if task.capability == "booking.verify":
            return self._verify(task, booking, evidence, seen)
        return self._prepare(task, booking, evidence, seen)

    def _verify(self, task: TeamTask, booking: dict, evidence: list,
                seen: set[str]) -> TeamResult:
        """★공급자 쪽 상태와 **대조**한다. 우리 기록만 보고 확정하지 않는다."""
        supplier = self._read(task, "read.supplier",
                              {"booking_id": booking.get("booking_id")}, seen)
        evidence = self._evidence(task, source_id="read.supplier",
                                  claim="공급자 예약 상태", value=supplier, base=evidence)
        if supplier is None:
            return self._unknown(task, "공급자 예약 상태", evidence)

        matches = supplier.get("status") == booking.get("status")
        return self._result(
            task, outcome="completed", confidence=1.0, evidence=evidence,
            next_action=NextAction.RESPOND,
            answer=("예약 상태가 공급자 기록과 일치합니다." if matches else
                    "예약 상태가 공급자 기록과 다릅니다. 사람이 확인해야 합니다."),
            decisions=[{"matches_supplier": matches}],
            warnings=[] if matches else ["우리 기록과 공급자 기록이 어긋난다"])

    def _prepare(self, task: TeamTask, booking: dict, evidence: list,
                 seen: set[str]) -> TeamResult:
        """바꿔야 할 것·대안·차액을 정리해 **제안**으로 만든다."""
        policy = self._read(task, "read.policy", {"query": task.input_text}, seen)
        evidence = self._evidence(task, source_id="read.policy",
                                  claim="변경·취소 규정", value=policy, base=evidence)
        if not policy:
            return self._unknown(task, "변경·취소 규정", evidence)

        action = ("booking.cancel" if task.capability == "booking.prepare_cancel"
                  else "booking.change")
        proposal = self._proposal(
            task, action,
            {"booking_id": booking.get("booking_id"), "reason": task.input_text},
            evidence)
        return self._result(
            task, outcome="completed", confidence=0.8, evidence=evidence,
            next_action=NextAction.WAIT_FOR_APPROVAL,
            answer="바꿔야 할 내용을 정리했습니다. 승인 뒤 업체에 인계됩니다.",
            action_proposals=[proposal],
            decisions=[{"prepared": action}])
