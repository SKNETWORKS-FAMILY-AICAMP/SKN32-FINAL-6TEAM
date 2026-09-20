# -*- coding: utf-8 -*-
"""Case 버전의 **일정 관리** — activity · dining · mobility Team 이 같이 쓰는 부품.

★`[결정 2026-09-17]` 시나리오용 여행 버전(`trip_watch`·`trip_desk`)이 하던 일을 Case 로 한다.

    Case(대상 = 여행)  →  Controller  →  Team 이 **읽고 계산해서 제안**  →  코어가 적용·통지

★Team 은 쓰지 않는다. 계산 결과를 `itinerary.apply` 제안(승인 불요 · 위험 낮음)으로 낸다.
  적용과 통지는 코어가 Case 완료와 한 트랜잭션으로 한다(`app/core/actions.py`).

★계산은 `itinerary_changes.py` 하나다 — 시나리오 버전과 **같은 함수**라 문구·판단이 같다.

★읽기는 전부 도구로 한다(`read.itinerary` · `read.itinerary_version` · `read.place_catalog` ·
  `read.disruptions` · `read.route_events` · `read.customer_report`). 도구가 모르면(`None`)
  지어내지 않고 escalate 한다.

누가 무엇을 하나:

    공통      change(다른 안으로) · rollback(되돌리기)
    activity  감시 Case(성립 점검 disrupted → 대안) · stock_out(동선 위 매장, 일정 안 바꿈)
    dining    delay(늦음) · closed(휴무)
    mobility  감시 Case(구간 사건 → 경로 재선택)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.contracts import ActionProposal, NextAction, TeamResult, TeamTask
from app.core.idempotency import idempotency_key

from .itinerary import Item, item_from_dict
from .itinerary_actions import ACTION_TYPE, change_arguments
from .itinerary_changes import ItineraryChange, NoChange, plan_rollback, plan_swap

KST = ZoneInfo("Asia/Seoul")

#: 일정 관리에 쓰는 읽기 도구 — 각 Team 의 manifest 가 필요한 만큼 더한다.
ITINERARY_TOOLS = ["read.itinerary", "read.itinerary_version", "read.place_catalog",
                   "read.customer_report"]

#: 바꾸지 않아도 되는 결과 — 사람에게 넘길 일이 아니라 **답**이다(시나리오 화면 문구와 같다).
ANSWERS = {
    "still_fits": "지금 일정 그대로도 괜찮아요 — 바꾸지 않았어요.",
    "no_meal": "그 시각 뒤에는 식사 일정이 없어요.",
    "no_alternate": "바꿀 수 있는 다른 안이 없어요.",
    "clear": "지금 확인해 보니 일정에 영향이 없어요 — 바꾸지 않았어요.",
    "gone": "그 일정은 이미 바뀌었어요 — 다시 바꾸지 않았어요.",
}


class ItineraryWork:
    """`TravelTeamBase` 를 상속한 Team 에 섞는다. `manifest.team_id` 로 자기 capability 를 안다."""

    # ── 선택 ────────────────────────────────────────────────────
    @property
    def itinerary_capability(self) -> str:
        return f"{self.manifest.team_id}.itinerary"

    @classmethod
    def _wants_itinerary(cls, state: dict[str, Any]) -> bool:
        ref = (state or {}).get("subject_ref") or {}
        return ref.get("kind") == "trip" and bool(ref.get("id"))

    # ── 진입 ────────────────────────────────────────────────────
    async def run_itinerary(self, task: TeamTask) -> TeamResult:
        state = task.context.current_state
        ref = state.get("subject_ref") or {}
        seen: set[str] = set()
        view = self._read(task, "read.itinerary", {"trip_id": ref.get("id")}, seen)
        evidence = self._evidence(task, source_id="read.itinerary", claim="현재 일정 버전", value=view)
        if view is None:
            return self._unknown(task, "여행 일정", evidence)
        trip = view["trip"]
        items = [item_from_dict(entry) for entry in view["items"]]
        request = dict(ref.get("request") or {})
        at = self._moment(request.get("at") or (state.get("trigger") or {}).get("at"))
        ctx = {"seen": seen, "evidence": evidence, "trip": trip, "items": items, "ref": ref,
               "request": request, "at": at}

        if state.get("trigger_source") == "schedule":
            return await self.handle_trigger(task, ctx)

        kind = request.get("type")
        report: dict[str, Any] = {}
        reading = (state.get("interpretation") or {}).get("report")
        if not kind and isinstance(reading, dict) and reading.get("type"):
            # ★접수가 분류 직전에 이미 뽑았다 — 같은 문장을 모델에 두 번 묻지 않는다.
            report, kind = reading, reading["type"]
            ctx["evidence"] = self._evidence(task, source_id="case.interpretation",
                                             claim="접수 때 고객 문장에서 뽑은 신고", value=report,
                                             base=ctx["evidence"])
            if kind == "other":
                return self._escalate(task, "report_not_understood", ctx["evidence"])
        if not kind:
            report = self._read(task, "read.customer_report", {"text": task.input_text}, seen) or {}
            ctx["evidence"] = self._evidence(task, source_id="read.customer_report",
                                             claim="고객 문장에서 뽑은 신고", value=report or None,
                                             base=ctx["evidence"])
            if not report:
                return self._unknown(task, "신고 내용", ctx["evidence"])
            kind = report.get("type")
            if not kind or kind == "other":
                return self._escalate(task, "report_not_understood", ctx["evidence"],
                                      warnings=[str(report.get("error") or "일정을 바꿀 신고로 읽히지 않는다")])
        ctx["report"] = {**report, **request}
        if kind == "change":
            return self._change(task, ctx)
        if kind == "rollback":
            return self._rollback(task, ctx)
        return await self.handle_report(task, kind, ctx)

    # ── 팀별로 채운다 ───────────────────────────────────────────
    async def handle_trigger(self, task: TeamTask, ctx: dict[str, Any]) -> TeamResult:
        return self._escalate(task, "trigger_not_handled_by_team", ctx["evidence"])

    async def handle_report(self, task: TeamTask, kind: str, ctx: dict[str, Any]) -> TeamResult:
        return self._escalate(task, f"report_{kind}_not_handled_by_team", ctx["evidence"])

    # ── 공통: 다른 안으로 · 되돌리기 ─────────────────────────────
    def _change(self, task: TeamTask, ctx: dict[str, Any]) -> TeamResult:
        ref, trip, items = ctx["ref"], ctx["trip"], ctx["items"]
        target = ref.get("part_id") or ref.get("recent_part_id")
        if not target:
            return self._unknown(task, "바꿀 일정 항목", ctx["evidence"])
        item = next((i for i in items if str(i.item_id) == str(target)), None)
        if item is not None and item.kind != self.manifest.team_id:
            return self._escalate(task, "target_kind_mismatch", ctx["evidence"],
                                  warnings=[f"{item.kind} 항목은 {self.manifest.team_id} 팀 일이 아니다"])
        places = self.catalog(task, ctx)
        if places is None:
            return self._unknown(task, "장소 목록", ctx["evidence"])
        check = self.recheck(task, ctx) if self.manifest.team_id == "activity" else None
        plan = plan_swap(trip_version=trip["version"],
                         base_version=int(ref.get("base_version") or trip["version"]),
                         items=items, places_by_id={p["place_id"]: p for p in places},
                         item_id=UUID(str(target)), choice=ctx["request"].get("choice"),
                         message=task.input_text, request_id=task.context.current_state.get("request_id"),
                         check=check)
        return self.settle(task, ctx, plan)

    def _rollback(self, task: TeamTask, ctx: dict[str, Any]) -> TeamResult:
        ref, trip, items = ctx["ref"], ctx["trip"], ctx["items"]
        to_version = ctx["report"].get("to_version")
        if to_version is None:
            return self._unknown(task, "되돌릴 버전", ctx["evidence"])
        base = int(ref.get("base_version") or trip["version"])
        old: list[Item] = []
        if trip["version"] == base and 1 <= int(to_version) < trip["version"]:
            view = self._read(task, "read.itinerary_version",
                              {"trip_id": trip["trip_id"], "version": int(to_version)}, ctx["seen"])
            ctx["evidence"] = self._evidence(task, source_id="read.itinerary_version",
                                             claim=f"일정 버전 {to_version}", value=view, base=ctx["evidence"])
            if view is None:
                return self._unknown(task, "되돌릴 일정 버전", ctx["evidence"])
            old = [item_from_dict(entry) for entry in view["items"]]
        plan = plan_rollback(trip_version=trip["version"], base_version=base, current_items=items,
                             old_items=old, to_version=int(to_version), message=task.input_text,
                             request_id=task.context.current_state.get("request_id"))
        return self.settle(task, ctx, plan)

    # ── 도우미 ──────────────────────────────────────────────────
    def catalog(self, task: TeamTask, ctx: dict[str, Any]) -> list[dict[str, Any]] | None:
        if "places" not in ctx:
            ctx["places"] = self._read(task, "read.place_catalog", {}, ctx["seen"])
            ctx["evidence"] = self._evidence(task, source_id="read.place_catalog", claim="대안 후보 장소",
                                             value=ctx["places"], base=ctx["evidence"])
        return ctx["places"]

    def recheck(self, task: TeamTask, ctx: dict[str, Any]):
        """대안을 **그 시각에 다시 점검**하는 콜러블 — 점검기는 도구로만 부른다.

        ★도구가 모르면(`None`) 「clear」로 읽지 않는다 — `fatal` 로 돌려 그 후보를 탈락시킨다.
        """
        def check(*, place: dict[str, Any], starts_at: datetime | None) -> dict[str, Any]:
            report = self._read(task, "read.disruptions", self.check_arguments(place, starts_at), ctx["seen"])
            return report if isinstance(report, dict) else {"verdict": "fatal", "unknown": True}
        return check

    @staticmethod
    def check_arguments(place: dict[str, Any], starts_at: datetime | None) -> dict[str, Any]:
        return {"place_id": place.get("place_id"), "latitude": place.get("latitude"),
                "longitude": place.get("longitude"), "weather_sensitive": place.get("weather_sensitive"),
                "district": place.get("district"),
                "starts_at": starts_at.isoformat() if starts_at else None}

    @staticmethod
    def _moment(value: Any) -> datetime:
        if value:
            moment = datetime.fromisoformat(str(value))
            return moment if moment.tzinfo else moment.replace(tzinfo=KST)
        return datetime.now(KST)

    def settle(self, task: TeamTask, ctx: dict[str, Any], plan: ItineraryChange | NoChange) -> TeamResult:
        """계산 결과 → Team 결과. 바꾸면 제안 + 통지 문구, 안 바꾸면 답 또는 사람에게."""
        evidence = ctx["evidence"]
        if isinstance(plan, NoChange):
            if plan.status in ANSWERS:
                return self._result(task, outcome="completed", confidence=0.9, evidence=evidence,
                                    answer=ANSWERS[plan.status], next_action=NextAction.RESPOND,
                                    decisions=[{"itinerary": plan.status, **self._plain(plan.detail)}])
            return self._escalate(task, f"itinerary_{plan.status}", evidence,
                                  warnings=[f"일정을 바꾸지 못했다: {plan.status}"])
        trip = ctx["trip"]
        base = int(ctx["ref"].get("base_version") or trip["version"]) \
            if plan.reason in ("customer_request", "rollback") else trip["version"]
        arguments = change_arguments(trip_id=trip["trip_id"], base_version=base, change=plan)
        proposal = ActionProposal(
            action_type=ACTION_TYPE, arguments=arguments,
            idempotency_key=idempotency_key(
                tenant_id=task.context.tenant_id,
                request_id=str(task.context.current_state.get("request_id") or task.case_id),
                action_type=ACTION_TYPE, business_subject=f"{trip['trip_id']}:v{base}"),
            # ★우리 DB 안의 일정 버전만 바꾼다(v11 §4-C) — 승인 없이 먼저 고치고 알린다.
            #   근거 대조는 적용기가 적용 순간에 한다(기준 버전 · 항목 · 장소 실재).
            approval_required=False, risk_level="low", rationale_evidence_ids=[])
        return self._result(task, outcome="completed", confidence=0.9, evidence=evidence,
                            answer=plan.notice["text"], next_action=NextAction.RESPOND,
                            action_proposals=[proposal],
                            decisions=[{"itinerary": plan.reason, **self._plain(plan.summary)}])

    @staticmethod
    def _plain(value: dict[str, Any]) -> dict[str, Any]:
        import json

        return json.loads(json.dumps(value, ensure_ascii=False, default=str))


__all__ = ["ANSWERS", "ITINERARY_TOOLS", "ItineraryWork"]
