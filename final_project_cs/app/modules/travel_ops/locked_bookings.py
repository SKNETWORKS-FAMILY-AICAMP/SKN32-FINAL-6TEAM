# -*- coding: utf-8 -*-
"""Lodging · Flight — **등록만 · 로직 없음 · 잠긴 예약 취급.**

★껍데기 Team 은 혼란을 만든다. 커머스의 `voc_store_manager` 가 계약만 있고
  동작이 없어 "이 팀은 뭘 하나" 를 매번 다시 확인해야 했다.
  그래서 **첫 줄에 무엇인지 적는다.**

이 둘은 코어 조립이 건드리지 않아야 하는 예약이다. 후보 형태의
`locked: true` 에 대응하고, **어떤 변경 제안도 만들지 않는다.**
"""
from __future__ import annotations

from app.core.contracts import NextAction, TeamManifest, TeamResult, TeamTask

from ._base import TravelTeamBase


class _LockedBookingTeam(TravelTeamBase):
    """조회만 하고 아무것도 제안하지 않는다."""

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked

        seen: set[str] = set()
        booking = self._read(task, "read.booking", {"case_id": str(task.case_id)}, seen)
        evidence = self._evidence(task, source_id="read.booking",
                                  claim="잠긴 예약", value=booking)
        if booking is None:
            return self._unknown(task, "예약 내역", evidence)

        return self._result(
            task, outcome="completed", confidence=1.0, evidence=evidence,
            next_action=NextAction.RESPOND,
            answer="이 예약은 잠긴 예약으로 취급합니다. 일정 조정 대상이 아닙니다.",
            decisions=[{"locked": True, "team": self.manifest.team_id}])


class LodgingTeam(_LockedBookingTeam):
    manifest = TeamManifest(
        team_id="lodging",
        display_name="Lodging Team (등록만)",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["lodging.status"],
        accepted_case_types=["lodging"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.booking"],
        knowledge_scope=["lodging"],
        max_steps=2,
        active=True,
        implementation_revision="2026-09-09",
        default_capability="lodging.status",
    )


class FlightTeam(_LockedBookingTeam):
    manifest = TeamManifest(
        team_id="flight",
        display_name="Flight Team (등록만)",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["flight.status"],
        accepted_case_types=["flight"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.booking"],
        knowledge_scope=["flight"],
        max_steps=2,
        active=True,
        implementation_revision="2026-09-09",
        default_capability="flight.status",
    )
