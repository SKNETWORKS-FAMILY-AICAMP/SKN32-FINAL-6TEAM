# -*- coding: utf-8 -*-
"""Dining Team — 그 시각에 그 식당이 여는지, 조건이 맞는지 본다.

★**「오늘 여는지」가 아니라 「그 일정 시각에 여는지」**를 본다.

★확인 수준을 같이 남긴다. 제공자의 영업시간은 **오늘부터 며칠의 예정**이지
  조회 순간의 개점 확인이 아니다(v10 §4-D). 재조회 시각을 현장 관찰 시각처럼
  표시하면 안 된다 — `confirmed_at` 과 출처를 함께 담는다.
"""
from __future__ import annotations

from typing import Any

from app.core.contracts import NextAction, TeamManifest, TeamResult, TeamTask

from ._base import TravelTeamBase
from .itinerary_changes import plan_closed, plan_delay
from .itinerary_team import ITINERARY_TOOLS, ItineraryWork


class DiningTeam(ItineraryWork, TravelTeamBase):
    manifest = TeamManifest(
        team_id="dining",
        display_name="Dining Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["dining.check_open", "dining.check_conditions",
                      "dining.itinerary"],   # ★`[2026-09-17]` 여행 일정 관리 — 늦음 · 휴무 · 재요청
        accepted_case_types=["dining"],
        # ★`[2026-09-17]` `policy` 를 뺐다 — 이 Team 은 정책 문서를 판단에 쓰지 않는다(선언만 있었다).
        # ★`[2026-09-22]` **되돌렸다.** 여행 코퍼스가 생겨 이 scope 에 문서가 있다
        #   (조정·노쇼 기준 `t_doc_06`, 대체 식당 판정 `t_doc_07`, 동행 조건 `t_doc_12`).
        #   ★단 **「이 집이 할랄인가」는 여전히 RAG 가 아니다** — 그건 사실이라 `read.place` 가 댄다.
        #   코퍼스에는 「무엇이 확인되면 가능하다고 말해도 되나」만 들어 있다(t_doc_12 §조건은 사실이고…).
        required_context=["case_state", "policy", "db_facts", "history"],
        policy_optional_capabilities=["dining.itinerary"],
        allowed_tools=["read.place", "read.policy", "read.booking", *ITINERARY_TOOLS],
        # ★`[2026-09-22]` `opening_hours`·`dietary` 는 **실물이 없던 scope** 였다(문서 0건). 지운다 —
        #   안 쓰는 선언은 나중에 누가 잘못 채운다(재점검 문서 §1 이 지적한 그대로).
        knowledge_scope=["travel_dining", "travel_cancellation", "travel_access"],
        max_steps=12,
        active=True,
        implementation_revision="2026-09-22",
        default_capability="dining.check_open",
    )

    @staticmethod
    def select_capability(intent: str | None, input_text: str, state: dict | None = None) -> str | None:
        """★여행이 정해진 Case 는 일정 관리로 — 그 밖은 기본 동작에 맡긴다."""
        return "dining.itinerary" if ItineraryWork._wants_itinerary(state or {}) else None

    async def handle_report(self, task: TeamTask, kind: str, ctx: dict[str, Any]) -> TeamResult:
        if kind not in ("delay", "closed"):
            return await super().handle_report(task, kind, ctx)
        places = self.catalog(task, ctx)
        if places is None:
            return self._unknown(task, "장소 목록", ctx["evidence"])
        request_id = task.context.current_state.get("request_id")
        if kind == "delay":
            minutes = ctx["report"].get("minutes")
            if not minutes:
                return self._unknown(task, "늦는 시간", ctx["evidence"])
            plan = plan_delay(trip=ctx["trip"], items=ctx["items"], places=places, at=ctx["at"],
                              minutes=int(minutes), message=task.input_text, request_id=request_id)
        else:
            plan = plan_closed(trip=ctx["trip"], items=ctx["items"], places=places, at=ctx["at"],
                               message=task.input_text, request_id=request_id)
        return self.settle(task, ctx, plan)

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked
        if task.capability == self.itinerary_capability:
            return await self.run_itinerary(task)

        seen: set[str] = set()
        # ★★2026-09-09 결함 수정. 전에는 `read.place` 를 `case_id` 로 불렀다.
        #   장소 조회의 열쇠는 **`place_id`** 이고 그건 예약에 들어 있다 —
        #   Case 번호로는 어느 장소인지 알 수 없다. 실 DB 종단 실행에서
        #   Dining 이 항상 `unknown_장소·영업 정보` 로 떨어져 드러났다.
        #   Activity 는 처음부터 예약을 먼저 읽고 있었다 — **같은 팀 안에서도
        #   갈라졌던** 것이고, 그래서 종단 실행이 필요했다.
        booking = self._read(task, "read.booking", {"case_id": str(task.case_id)}, seen)
        evidence = self._evidence(task, source_id="read.booking",
                                  claim="예약 내역", value=booking)
        if booking is None:
            return self._unknown(task, "예약 내역", evidence)

        place = self._read(task, "read.place",
                           {"place_id": booking.get("place_id")}, seen)
        evidence = self._evidence(task, source_id="read.place",
                                  claim="장소·영업 정보", value=place, base=evidence)
        if place is None:
            return self._unknown(task, "장소·영업 정보", evidence)

        # ★확인 시각이 없으면 "확인했다" 고 말하지 않는다.
        confirmed_at = place.get("confirmed_at")
        if confirmed_at is None:
            return self._unknown(task, "영업 정보의 확인 시각", evidence)

        if task.capability == "dining.check_conditions":
            return self._conditions(task, place, evidence)

        open_at_slot = place.get("open_at_slot")
        if open_at_slot is None:
            return self._unknown(task, "그 시각의 영업 여부", evidence)

        return self._result(
            task, outcome="completed", confidence=0.9, evidence=evidence,
            next_action=NextAction.RESPOND,
            answer=(f"일정 시각에 영업합니다(확인 시각 {confirmed_at})."
                    if open_at_slot else
                    f"일정 시각에는 영업하지 않습니다(확인 시각 {confirmed_at})."),
            decisions=[{"open_at_slot": open_at_slot,
                        "confirmed_at": str(confirmed_at)}],
            warnings=["제공자 예정 정보이지 현장 확인이 아니다"])

    def _conditions(self, task: TeamTask, place: dict, evidence: list) -> TeamResult:
        """동행 조건 — 아이 동반 · 할랄 · 채식. ★모르는 조건은 「모름」으로 둔다."""
        wanted = task.context.current_state.get("dietary") or []
        known = place.get("dietary") or []
        absent = place.get("dietary_absent") or []
        unknown = [item for item in wanted if item not in known and item not in absent]
        if unknown:
            return self._unknown(task, f"조건 {', '.join(unknown)}", evidence)

        met = [item for item in wanted if item in known]
        return self._result(
            task, outcome="completed", confidence=0.9, evidence=evidence,
            next_action=NextAction.RESPOND,
            answer=(f"요청한 조건을 모두 만족합니다 — {', '.join(met)}." if met else
                    "요청한 조건이 없어 별도 확인 없이 진행할 수 있습니다."),
            decisions=[{"conditions_met": met, "requested": list(wanted)}])
