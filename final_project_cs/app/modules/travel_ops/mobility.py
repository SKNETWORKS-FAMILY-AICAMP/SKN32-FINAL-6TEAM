# -*- coding: utf-8 -*-
"""Mobility Team — 구간 이동이 일정 안에 들어가는지 본다.

★**문의와 사건을 가른다.** "막차가 몇 시인가요"(문의)와 "막차를 놓쳤어요"(사건)는
  다른 capability 다. 커머스에서 이 문구 판정이 지나치게 넓어 "지연 **기준**이
  어떻게 되나요" 같은 문의까지 예외로 잡은 적이 있다 — **요청을 분명히 밝히는
  문구만 잡고, 신호가 없으면 기본 동작(조회)에 맡긴다.**
"""
from __future__ import annotations

from app.core.contracts import NextAction, TeamManifest, TeamResult, TeamTask

from ._base import TravelTeamBase


class MobilityTeam(TravelTeamBase):
    manifest = TeamManifest(
        team_id="mobility",
        display_name="Mobility Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["mobility.check_route", "mobility.status", "mobility.exception"],
        accepted_case_types=["mobility"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.route", "read.transit", "read.policy"],
        knowledge_scope=["mobility", "transit", "route_exception"],
        max_steps=6,
        active=True,
        implementation_revision="2026-09-09",
        default_capability="mobility.check_route",
    )

    #: ★사건을 **분명히 밝히는** 문구만 잡는다. 물음표로 끝나는 문의는 안 잡는다.
    #:  커머스에서 이 훅이 넓어 문의를 사건으로 잘못 잡은 적이 있다.
    _INCIDENT_MARKERS = ("놓쳤", "못 탔", "끊겼", "지연됐", "결항", "운행 중단")

    @staticmethod
    def select_capability(intent: str | None, input_text: str) -> str | None:
        if intent != "mobility":
            return None
        if any(marker in input_text for marker in MobilityTeam._INCIDENT_MARKERS):
            return "mobility.exception"
        return None   # 신호가 없으면 기본 동작에 맡긴다

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked

        seen: set[str] = set()
        route = self._read(task, "read.route", {"case_id": str(task.case_id)}, seen)
        evidence = self._evidence(task, source_id="read.route",
                                  claim="구간 정보", value=route)
        if route is None:
            return self._unknown(task, "구간 정보", evidence)

        transit = self._read(task, "read.transit",
                             {"route_id": route.get("route_id")}, seen)
        evidence = self._evidence(task, source_id="read.transit",
                                  claim="운행 정보", value=transit, base=evidence)
        if transit is None:
            return self._unknown(task, "운행 정보", evidence)

        # ★여유 시간은 계산이다. LLM 을 부르지 않는다.
        need = route.get("duration_minutes")
        have = route.get("gap_minutes")
        if need is None or have is None:
            return self._unknown(task, "이동 시간 또는 여유 시간", evidence)

        fits = have >= need
        last_ok = transit.get("last_departure_ok")
        return self._result(
            task, outcome="completed", confidence=1.0, evidence=evidence,
            next_action=NextAction.RESPOND,
            answer=(f"이동이 일정 안에 들어갑니다 — 필요 {need}분, 여유 {have}분."
                    if fits else
                    f"이동 시간이 부족합니다 — 필요 {need}분인데 여유가 {have}분입니다."),
            decisions=[{"fits": fits, "need_minutes": need, "gap_minutes": have,
                        "last_departure_ok": last_ok}],
            warnings=[] if last_ok is not False else ["막차 시각을 넘긴다"])
