# -*- coding: utf-8 -*-
"""분류 에이전트의 검증된 계획으로 같은 여행의 문제를 최신 초안 위에서 처리한다.

로컬 TeamExecutorPort가 여행 묶음을 받고, 각 항목은 등록된 소유 Team의 도구·예산으로 계산한다.
Activity를 조정자로 두지 않으며 실행 순서·우선순위·의존관계는 모델 계획에 남긴다.
계획 실패는 고정 순서로 대신하지 않는다. 실패 항목과 그 의존 작업은 기존 일정을 유지하며
고객에게 확인 시각·오류 코드를 알리고 다음 회차에 다시 확인한다. 독립 항목은 계속 처리한다.
누적·최종 전체 재검증 후 적용 제안 하나를 내며 실제 저장은 코어의 기존 트랜잭션을 쓴다.
항로 지킴이 직접 켜짐만 자동 변경하고 고정·재난 정지·업체 거래 승인은 별도 경계를 따른다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from time import perf_counter       # 항목별 소요 시간 — 위 `time`(마감 시계)과 따로 둔다(시험이 마감 시계만 바꿔 끼울 수 있게)
from dataclasses import dataclass, field
from copy import copy
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import ActionProposal, NextAction, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.core.settings import get_guardrails
from app.core.service_bindings import current_bindings, read_binding
from app.core.team_availability import TeamUnavailable

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.actions.itinerary_actions import ACTION_TYPE, change_arguments, introduced_violations
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, NoChange, refresh_moves_around
from app.domains.travel_ops.components.itinerary.itinerary_fit import fit_change
from app.domains.travel_ops.instances._shared.itinerary_team import Consent
from app.domains.travel_ops.components.team_hooks import watch_planners
from app.domains.travel_ops.components.planning.pending import Decision, _cause_text as cause_text, cause_fingerprint, decide, is_safety
from app.domains.travel_ops.components.planning.execution_plan import PlanFailed, classify_plan
from app.domains.travel_ops.components.watch.risk_report import CATEGORIES

logger = logging.getLogger(__name__)

#: 감시 대상 종류. 실행 순서는 검증된 분류 에이전트 계획만 정한다.
WATCH_KINDS = frozenset({"activity", "dining", "mobility"})
_COUNT_WORD = {2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉"}


@dataclass
class Outcome:
    item: Item
    kind: str
    causes: list[dict[str, Any]] = field(default_factory=list)
    change: ItineraryChange | None = None
    reasons: list[str] = field(default_factory=list)
    decision: Decision | None = None
    indoor_unknown: bool = True
    #: ★`[2026-10-03]` 이 항목 계산에 쓴 시간(초)과 도구 호출 수 — 병목을 **재서** 찾으려고 Case 결정 기록(`decisions[].timing`)에 남긴다
    seconds: float = 0.0
    calls: int = 0
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def safety(self) -> bool:
        # 자료 조회 실패는 재난 발생 사실이 아니다. 확인한 사건만 안전 안내로 구분한다.
        return is_safety({"disruptions": [c for c in self.causes if c.get("kind") != "source_unavailable"]})


def _planner(kind: str):
    """항목 종류 → 계산 함수. ★`[2026-10-06]` 세 팀을 직접 부르지 않는다 — 팀이 조립 때 꽂은
    자리에서 받는다(D-CS-013 `components/team_hooks/watch_planners.py`). 그 팀이 조립에 없으면
    `None` 이고, 그 종류의 문제는 처리되지 않는다 — **다른 팀 계산으로 대신하지 않는다.**
    ☆전에는 세 팀 모듈이 `itinerary_team` 을 불러 순환이 생겨 함수 안에서 늦게 불러야 했다."""
    return watch_planners.planner(kind)


def unavailable_reason(kind: str) -> str | None:
    """고정된 조립 판에서 감시 종류의 소유자와 계산 연결을 함께 확인한다."""
    table = current_bindings()
    if kind not in WATCH_KINDS:
        return None
    if table is None:
        read_binding("watch_planners", kind, True, required_team=kind)
        return None  # 명시적으로 조립한 단독 부품의 기존 호출 계약.
    if table.registry is None:
        return "not_installed"
    try:
        table.registry.require_runnable(kind)
    except TeamUnavailable as exc:
        return exc.reason
    return None if table.values.get(("watch_planners", kind)) is not None else "not_installed"


def skipped_watch(kind: str, *, trip_id, item_id) -> dict[str, Any] | None:
    reason = unavailable_reason(kind)
    if reason is None:
        return None
    table = current_bindings()
    logger.warning("watch_kind_unavailable kind=%s reason=%s composition_revision=%s",
                   kind, reason, table.revision)
    return {"trip_id": str(trip_id), "item_id": str(item_id), "kind": kind,
            "reason": reason, "verdict": "skipped"}


# ── 고객에게 보일 문장 ─────────────────────────────────────────

def _head(count: int) -> str:
    return f"일정에 문제가 {_COUNT_WORD.get(count, str(count))} 가지 겹쳐서 이렇게 처리했어요."


def _confirmed_text(causes: list[dict[str, Any]]) -> str:
    """조회 오류와 구분해 확인한 사실만 적는다. 주변 통제를 실제 이동 경로로 확정하지 않는다."""
    facts = []
    for cause in causes:
        if cause.get("kind") == "source_unavailable":
            continue
        category = cause.get("category")
        label = "장소 주변 교통 통제" if category == "traffic_control" else CATEGORIES.get(category, "일정 관련 정보")
        evidence = cause.get("text") or cause.get("message") or cause_text([cause])
        location = " · ".join(str(cause[k]) for k in ("road", "section") if cause.get(k))
        fact = f"{label}: " + (f"{location} — " if location else "") + str(evidence)
        if cause.get("source"):
            fact += f" (출처: {cause['source']}"
            if cause.get("confirmed_at"):
                fact += f", 자료 확인 시각: {cause['confirmed_at']}"
            fact += ")"
        facts.append(fact)
    return "; ".join(dict.fromkeys(facts))


def _line(outcome: Outcome) -> str:
    """항목 하나의 한 줄 — 원인에 있는 말만(`cause_text`). 지어낸 대안 · 약속 없음, 사람 대기 약속도 안 한다."""
    title, why = outcome.item.title, cause_text(outcome.causes)
    if outcome.kind in ("source_failed", "error", "retry"):
        code = outcome.reasons[0] if outcome.reasons else outcome.kind
        confirmed = _confirmed_text(outcome.causes)
        if confirmed:
            failed = sorted({CATEGORIES.get(c.get("category"), "필수 자료") for c in outcome.causes
                             if c.get("kind") == "source_unavailable"})
            missing = f"({', '.join(failed)})" if failed else ""
            return (f"{title} — 확인한 정보: {confirmed}. 일부 자료{missing}를 확인하지 못해 "
                    "자동 변경을 보류하고 기존 일정을 유지했어요. 자료와 조건을 다시 확인할게요. "
                    f"확인 시각: {outcome.checked_at}, 오류 코드: {code}.")
        return (f"{title} — 이번 회차에 확인을 끝내지 못해 기존 일정을 유지했어요. "
                f"자료와 조건을 다시 확인할게요. 확인 시각: {outcome.checked_at}, 오류 코드: {code}.")
    if outcome.kind == "unhandled":
        # ★`[2026-10-14]` 다시 시도하지 않는 실패(적용기 거절 · 모름 · 제안 검증 실패 · 시간 초과) — 다시 확인하겠다고 약속하지 않는다. 내부 문구는 싣지 않고 코드만
        code = outcome.reasons[0] if outcome.reasons else outcome.kind
        # ★`[2026-10-23 사용자 지시 — ST4F-723]` 고객 문장에 마크다운 별표를 넣지 않는다(아래 둘도) — 웹 알림이 `**…**` 를 그대로 보였다
        return (f"{title} — {why}. 자동으로 처리하지 못해 일정은 그대로 두었어요. "
                f"확인 시각: {outcome.checked_at}, 오류 코드: {code}.")
    if outcome.kind == "applied":
        change = outcome.change
        text = str(change.notice["text"])
        others = [str(name) for name in (change.notice.get("other_options") or [])]
        # 전달 쪽(`discord._compose`)과 같은 규칙 — 문장에 이미 「다른 안」이 있으면(식당 · 이동은 본문에 적는다) 또 붙이지 않는다
        return text + (f" 다른 안: {', '.join(others)}." if others and "다른 안" not in text else "")
    if outcome.kind == "asked":
        reason = outcome.decision.reason if outcome.decision else None
        how = {"protected": "변경하지 않기로 한 일정이라 바꾸지 않고, 어떻게 할지 따로 여쭤봤어요.",
               "safety_alert": "일정은 바꾸지 않았어요. 안전을 먼저 살펴 주세요 — 따로 여쭤봤어요.",
               }.get(str(reason), "먼저 물어보기로 하셔서 바꾸지 않고, 어떻게 할지 따로 여쭤봤어요.")
        return f"{title} — {why}. {how}"
    if outcome.kind == "consent":
        return f"{title} — {why}. 바꿀지 따로 여쭤봤어요."
    if outcome.kind == "recheck_failed":
        return f"{title} — {why}. 바꿀 곳을 찾았지만 일정 전체와 맞지 않아 일정은 그대로 두었어요."
    return f"{title} — {why}. 대신 갈 수 있는 곳을 찾지 못해 일정은 그대로 두었어요."       # no_alternate


#: 고객에게 말할 결과 — 안 바꿨거나 못 푼 것까지(바꾸지 않는 것과 알림을 끄는 것은 별개다)
_TELL = ("applied", "asked", "consent", "no_alternate", "recheck_failed", "unhandled", "source_failed", "error", "retry")
_UNCHANGED = ("no_alternate", "recheck_failed", "unhandled")
#: 기존 일정 유지·고객 안내와 함께 다음 회차에 다시 확인할 항목.
_RETRY = ("source_failed", "error", "retry")


def digest(outcomes: list[Outcome], *, kind: str) -> dict[str, Any]:
    """묶음의 알림 하나. `kind` — `change_notice`(판이 바뀜) · `guidance`(안 바꿨다). ★안전 사건 줄이 **앞**이고 하나라도 있으면 머리가 안전 알림이다."""
    # ★판이 바뀌면 묻는 항목도 한 줄씩 적는다(한 이야기로 읽히게). 안 바뀌면(`guidance`) 안 바꾼 것만 — 묻는 것은 제안마다 알림이 따로 있다
    told = [o for o in outcomes if o.kind in ((*_UNCHANGED, *_RETRY) if kind == "guidance" else _TELL)]
    told.sort(key=lambda o: (not o.safety,))                  # 안전 줄 먼저(나머지 순서는 그대로 — 안정 정렬)
    safety = any(o.safety for o in told)
    lines = [_line(o) for o in told]
    body = "\n".join(f"· {line}" for line in lines) if len(lines) > 1 else lines[0]
    if len(lines) > 1:
        body = _head(len(lines)) + "\n" + body
    if any(o.kind in _UNCHANGED for o in told):
        body += "\n가시기 전에 한 번 확인해 주세요."
    text = ("⚠️ 안전 알림 — " if safety else "") + body
    causes = [cause for o in told for cause in o.causes]
    kinds = {o.kind for o in told if o.kind in _UNCHANGED}
    payload: dict[str, Any] = {
        "type": "safety_alert" if safety else kind, "text": text, "language": "ko", "causes": causes, "changed": None,
        "other_options": [],            # 항목마다의 「다른 안」은 각 줄에 이미 적었다 — 전달 쪽이 또 붙이지 않게 비운다
        "replay": any(cause.get("mode") == "replay" for cause in causes), "batch": True,
        "items": [str(o.item.item_id) for o in told],
        # ★알림 키는 「항목 + 원인 지문」 한 규칙이다 — 같은 항목에 **다른 원인**(나중에 걸린 안전 사건)이 오면 다른 알림이다
        "keys": [f"{o.item.item_id}:{cause_fingerprint(o.causes)}" for o in told]}
    payload["deferred"] = [{"item_id": str(o.item.item_id), "code": o.reasons[0] if o.reasons else o.kind,
                            "checked_at": o.checked_at} for o in told if o.kind in _RETRY]
    # 다시 확인하지 않는 실패 — 같은 모양으로 따로 둔다(`deferred` 는 다음 회차에 다시 보는 것만)
    payload["unhandled"] = [{"item_id": str(o.item.item_id), "code": o.reasons[0] if o.reasons else o.kind,
                             "checked_at": o.checked_at} for o in told if o.kind == "unhandled"]
    if kind == "guidance":
        payload["kind"] = (next(iter(kinds)) if len(kinds) == 1 else "mixed") if kinds else "guidance"
        payload["reason"] = payload["kind"]
    else:
        payload["changes"] = [{"item_id": str(o.item.item_id), "text": o.change.notice["text"], "changed": o.change.notice.get("changed"),
                               "other_options": o.change.notice.get("other_options") or []}
                              for o in told if o.kind == "applied"]
    return payload


def guidance_key(payload: dict[str, Any]) -> str:
    """안 바꾼 것을 알리는 한 통의 키 — 같은 항목 · 같은 원인 집합이면 같은 키(같은 사건에 두 번 안 알린다)."""
    return hashlib.sha1(json.dumps(sorted(payload.get("keys") or []), ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


class WatchBatch:
    """한 여행의 감시 묶음 Case 를 푼다 — `ItineraryWork.run_itinerary` 가 트리거에 `batch` 가 있으면 부른다."""

    def __init__(self, work: Any, task: TeamTask, ctx: dict[str, Any], *, registry=None, planner=None,
                 diagnostic_recorder=None) -> None:
        self.work, self.task, self.ctx = work, task, ctx
        table = current_bindings()
        self.registry = registry or (table.registry if table is not None else None)
        self.planner = planner or classify_plan
        self.diagnostic_recorder = diagnostic_recorder
        self.plan = None
        self.step = None

    def _teams(self):
        manifests = self.registry.manifests() if self.registry else [self.work.manifest]
        return {m.team_id: {"tools": list(m.allowed_tools), "max_calls": m.max_steps}
                for m in manifests if m.active and f"{m.team_id}.itinerary" in m.capabilities
                and watch_planners.planner(m.team_id) is not None}

    def _scoped_work(self, step):
        """항목 소유 Team 의 모듈로, **실행 계획이 그 단계에 준** 도구·호출 예산으로 계산한다.

        ★`[2026-10-13]` 병합(2b5ad163)에서 이 함수가 두 벌 남아 뒤의 것(develop 판 — Team 기본 도구 전부, 계획 예산 무시)이
          앞의 것을 덮었다. 그래서 식사 항목도 활동 팀 설정으로 돌았고 계획의 호출 예산이 걸리지 않았다
          (test_classification_execution_plan 3건 실패). 계획 판을 남기고, develop 판이 하던 「연결 없는 단독 부품 시험은
          받은 그대로」를 합쳤다.
        """
        registry = self.registry
        if registry is None:
            return self.work, self.task
        source = registry.require_runnable(step.team_id, f"{step.team_id}.itinerary").module
        if source.manifest.team_id != step.team_id:
            raise PlanFailed("plan_team_unbound")
        work = copy(source)
        work.manifest = source.manifest.model_copy(update={"max_steps": step.max_calls})
        context = self.task.context.model_copy(update={"team_id": step.team_id,
                                                       "knowledge_scope": list(source.manifest.knowledge_scope)})
        scoped = TeamTask.model_validate({**self.task.model_dump(), "team_id": step.team_id,
                                         "capability": f"{step.team_id}.itinerary", "context": context,
                                         "allowed_tools": list(step.tools)})
        return work, scoped

    # ── 진입 ────────────────────────────────────────────────────
    def run(self) -> TeamResult:
        work, task, ctx = self.work, self.task, self.ctx
        trip, current = ctx["trip"], list(ctx["items"])
        constraints = trip.get("constraints") or {}
        entries = (task.context.current_state.get("trigger") or {}).get("batch") or []
        started_at = time.monotonic()
        try:
            self.plan = self.planner(query=task.input_text, trip=trip, items=current, issues=entries, teams=self._teams())
            # 주입한 모델도 동일 검증을 통과해야 한다. 검증된 모델 객체를 믿고 우회하지 않는다.
            from app.domains.travel_ops.components.planning.execution_plan import validate_plan
            by_id = {str(i.item_id): i for i in current}
            self.plan = validate_plan(self.plan.model_dump(), version=trip["version"],
                issues=[{**e, "kind": by_id[str(e["item_id"])].kind} for e in entries], teams=self._teams())
        except Exception as exc:  # 계획·제공자 실패는 성공으로 대체하지 않는다.
            self._diagnostic("classification_failed", error_code=str(exc) if isinstance(exc, PlanFailed) else "plan_invalid")
            return work._escalate(task, "classification_failed", ctx["evidence"],
                                  warnings=[f"retry:{e['item_id']}" for e in entries])
        wanted = [by_id[step.item_id] for step in self.plan.steps]
        guard = get_guardrails()
        # ★Team 코드는 동기라 `asyncio.wait_for` 가 도중에 끊지 못한다 — 새 항목을 시작하기 전에 스스로 시간을 본다
        stop_at = started_at + float(guard.get("reliability.team_timeout_seconds")) * float(guard.get("travel.watch.batch_time_ratio"))
        stop_at = min(stop_at, started_at + max(0, (task.deadline_at - datetime.now(UTC)).total_seconds()))

        draft, outcomes = list(current), []
        for self.step, original in zip(self.plan.steps, wanted):
            failed_dependencies = {str(o.item.item_id) for o in outcomes if o.kind not in ("applied", "nothing")}
            if set(self.step.depends_on) & failed_dependencies:
                outcomes.append(Outcome(original, "retry", reasons=["dependency_deferred"]))
                continue
            item = next((i for i in draft if i.item_id == original.item_id), None)
            if item is None:
                # 앞 항목을 고치며 이 항목(이동)이 새로 만들어졌다 — 이미 바뀐 것이다(마지막 재판정에서 그 변경이 빠지면 아래에서 `retry` 로 바뀐다)
                outcomes.append(Outcome(original, "nothing", reasons=["gone"]))
                continue
            if time.monotonic() >= stop_at:
                outcomes.append(Outcome(original, "retry", reasons=["deadline"]))
                continue
            ctx["items"], ctx["seen"] = draft, set()           # 초안 기준 · 항목마다 도구 예산을 따로
            started = perf_counter()
            outcome = self._one(item, trip, constraints)
            outcome.seconds, outcome.calls = round(perf_counter() - started, 3), len(ctx["seen"])
            outcomes.append(outcome)
            if outcome.kind == "applied":
                draft = outcome.change.new_items(draft)
        ctx["items"] = current

        outcomes = self._final_recheck(trip, current, outcomes)
        for outcome in outcomes:
            if outcome.kind in _RETRY:
                self._diagnostic(outcome.kind, item_id=str(outcome.item.item_id), error_code=outcome.reasons[0] if outcome.reasons else outcome.kind)
            elif any(str(e["item_id"]) == str(outcome.item.item_id) and e.get("attempt", 0) for e in entries):
                self._diagnostic("retry_recovered", item_id=str(outcome.item.item_id), result=outcome.kind)
        result = self._result(trip, current, outcomes)
        if not any("execution_plan" in d for d in result.decisions):
            result = result.model_copy(update={"decisions": [*result.decisions, {"execution_plan": self.plan.evidence()}]})
        return result

    def _diagnostic(self, code, **fields):
        from datetime import UTC, datetime
        diagnostic = {
            "event": "travel_execution_diagnostic", "tenant_id": self.task.context.tenant_id,
            "customer_id": str(self.task.context.current_state.get("customer_id") or ""),
            "case_id": str(self.task.case_id), "trip_id": str(self.ctx["trip"]["trip_id"]),
            "code": code, "checked_at": datetime.now(UTC).isoformat(),
            "plan_sha256": self.plan.evidence()["plan_sha256"] if self.plan else None, **fields}
        collection = None
        if self.diagnostic_recorder is not None:
            try:
                collection = self.diagnostic_recorder(diagnostic)
            except Exception:
                collection = {"status": "collection_degraded"}
            if collection.get("status") == "collection_degraded":
                logger.error("travel_diagnostic status=collection_degraded code=%s", code)
        logger.warning("travel_execution_diagnostic", extra={"diagnostic": diagnostic, "collection": collection})
        return collection

    # ── 항목 하나 ───────────────────────────────────────────────
    def _one(self, item: Item, trip: dict[str, Any], constraints: dict[str, Any]) -> Outcome:
        reason = unavailable_reason(item.kind)
        if reason is not None:
            skipped_watch(item.kind, trip_id=trip.get("trip_id"), item_id=item.item_id)
            return Outcome(item, "unavailable", reasons=[reason])
        planner = _planner(item.kind)
        if planner is None:
            return Outcome(item, "nothing", reasons=["unhandled_kind"])
        try:
            selected_work, selected_task = self._scoped_work(self.step)
            blocked = selected_work._guard(selected_task)
            plan = blocked if blocked is not None else planner(selected_work, selected_task, self.ctx, item)
        except TeamUnavailable as exc:
            logger.warning("watch_batch_team_unavailable kind=%s team_id=%s reason=%s composition_revision=%s",
                           item.kind, exc.team_id, exc.reason, getattr(current_bindings(), "revision", None))
            return Outcome(item, "unavailable", reasons=[exc.reason, exc.team_id])
        except Exception as exc:                # noqa: BLE001 — 한 항목의 예외가 묶음 전체(다른 항목 · 안전 사건 포함)를 막지 않는다. 세어서 남기고 그 항목만 다시 연다
            logger.exception("watch batch: item failed item=%s", item.item_id)
            return Outcome(item, "error", reasons=[type(exc).__name__])
        if isinstance(plan, TeamResult):
            code = plan.failure_code or ""
            return Outcome(item, "source_failed" if code == "fatal_source_failure" else "error", reasons=[code, *plan.warnings])
        if isinstance(plan, Consent):
            return Outcome(item, "consent", causes=list(plan.report.get("disruptions") or []),
                           indoor_unknown=bool(plan.report.get("indoor_unknown")))
        if isinstance(plan, NoChange):
            if plan.status == "unresolved":
                return Outcome(item, "no_alternate", causes=list((plan.detail or {}).get("causes") or []))
            return Outcome(item, "nothing", reasons=[plan.status])
        # ★일정 전체 재판정은 **묻는 안에도** 건다 — 단일 Case(`ItineraryWork.settle`)도 판정 문 앞에서 이미 걸렀다. 안 맞는 안을 「안 1」로 보내 고르게 두지 않는다
        fit = fit_change(plan, trip=trip, items=self.ctx["items"])
        if fit.change is None:
            return Outcome(item, "recheck_failed", causes=list(plan.causes),
                           reasons=[f"{s.rank}순위 {s.name} — {'; '.join(s.reasons)}" for s in fit.skipped])
        decision = decide(constraints=constraints, item=item, report={"disruptions": fit.change.causes})
        if decision.action != "apply":
            return Outcome(item, "asked", causes=list(fit.change.causes), change=fit.change, decision=decision)
        return Outcome(item, "applied", causes=list(fit.change.causes), change=fit.change)

    # ── 마지막 한 번 ────────────────────────────────────────────
    @staticmethod
    def _merged(current: list[Item], applied: list[Outcome]) -> tuple[list[Item], dict[Any, Item]]:
        replacements = {old: new for o in applied for old, new in o.change.replacements.items()}
        new_items = [replacements.get(i.item_id, i) for i in current]
        return refresh_moves_around(current, new_items, replacements), replacements

    def _final_recheck(self, trip: dict[str, Any], current: list[Item], outcomes: list[Outcome]) -> list[Outcome]:
        """합친 결과를 **적용기와 같은 방식으로**(한 번에 합쳐) 다시 판정한다. 걸리면 가장 나중 변경부터 하나씩 빼며 통과할 때까지 — 빠진 것은 `recheck_failed`.
        ★끝나면 「이미 바뀌었다」(`gone`)던 항목 가운데 **새 판에도 그대로 남은 것**을 `retry` 로 돌린다 — 그 항목을 바꾼다고 믿었던 변경이 빠졌다면 아무도 그 항목을 계산한 적이 없다."""
        while True:
            # 마지막 재검증에서 선행 변경이 빠지면 그 변경에 의존한 결과도 쓰지 않는다.
            failed = {str(o.item.item_id) for o in outcomes if o.kind not in ("applied", "nothing")}
            dependencies = {step.item_id: set(step.depends_on) for step in self.plan.steps} if self.plan else {}
            changed = False
            for outcome in outcomes:
                if outcome.kind in ("applied", "asked", "consent", "nothing") and dependencies.get(str(outcome.item.item_id), set()) & failed:
                    outcome.kind, outcome.reasons = "retry", ["dependency_deferred"]
                    failed.add(str(outcome.item.item_id))
                    changed = True
            if changed:
                continue
            applied = [o for o in outcomes if o.kind == "applied"]
            if not applied:
                break
            merged = self._merged(current, applied)[0]
            merged_ids = {i.item_id for i in merged}
            held = [o for o in outcomes if o.kind in (*_RETRY, "unavailable")]
            if any(o.item.item_id not in merged_ids for o in held):
                # 자동으로 새로 만든 이동이 조회 실패 항목을 덮으면 독립 변경이 아니다.
                dropped = applied[-1]
                dropped.kind, dropped.reasons = "recheck_failed", ["dependent_item_unverified"]
                continue
            introduced = introduced_violations(trip, current, merged)
            if not introduced:
                break
            dropped = applied[-1]
            dropped.kind, dropped.reasons = "recheck_failed", [v.reason for v in introduced]
        applied = [o for o in outcomes if o.kind == "applied"]
        final_ids = {i.item_id for i in (self._merged(current, applied)[0] if applied else current)}
        for outcome in outcomes:
            if outcome.kind == "nothing" and outcome.reasons == ["gone"] and outcome.item.item_id in final_ids:
                outcome.kind, outcome.reasons = "retry", ["gone_but_unchanged"]
        return outcomes

    # ── 결과 ────────────────────────────────────────────────────
    def _result(self, trip: dict[str, Any], current: list[Item], outcomes: list[Outcome]) -> TeamResult:
        work, task, ctx = self.work, self.task, self.ctx
        evidence = ctx["evidence"]
        applied = [o for o in outcomes if o.kind == "applied"]
        asked = [o for o in outcomes if o.kind == "asked"]
        consent = [o for o in outcomes if o.kind == "consent"]
        stuck = [o for o in outcomes if o.kind in _UNCHANGED]
        retry = [o for o in outcomes if o.kind in _RETRY]
        unavailable = [o for o in outcomes if o.kind == "unavailable"]
        summary = {kind: [o.item.title for o in outcomes if o.kind == kind]
                   for kind in ("applied", "asked", "consent", "no_alternate", "recheck_failed", "source_failed", "error", "retry", "nothing", "unavailable")}
        summary = {kind: titles for kind, titles in summary.items() if titles}
        warnings = [f"다시 열 항목 — {o.item.title}: {o.kind}({', '.join(o.reasons[:2])})" for o in retry]
        warnings += [f"미실행 항목 — {o.item.title}: team_unavailable({', '.join(o.reasons[:2])})" for o in unavailable]

        if not (applied or asked or consent):
            if unavailable and not (stuck or retry):
                first = unavailable[0]
                raise TeamUnavailable(first.reasons[1] if len(first.reasons) > 1 else first.item.kind, first.reasons[0])
            if stuck or retry:
                # 아무것도 못 바꿨다 — 단일 Case 와 같게 escalate 하고, 항목별 결과를 표지로 남긴다(`outcome:` 못 푼 것 → 감시가 고객에게 한 번에 알린다 · `retry:` 다시 열 것).
                #   다시 열 항목이 있으면 **다시 열 수 있는 사유**(`fatal_source_failure`)로 닫는다 — 그 항목이 영원히 막히지 않게
                code = ("fatal_source_failure" if retry or unavailable else
                        "itinerary_recheck_failed" if all(o.kind == "recheck_failed" for o in stuck) else "itinerary_unresolved")
                tokens = [*(f"outcome:{o.item.item_id}:{o.kind}" for o in [*stuck, *retry]),
                          *(f"retry:{o.item.item_id}" for o in [*retry, *unavailable])]
                return work._escalate(task, code, evidence, warnings=[*tokens, f"묶음 결과: {summary}"])
            return work.settle(task, ctx, NoChange("clear"))

        arguments, answer = self._arguments(trip, trip["version"], outcomes, applied, asked, consent, stuck, [*retry, *unavailable])
        proposal = ActionProposal(
            action_type=ACTION_TYPE, arguments=arguments,
            idempotency_key=idempotency_key(
                tenant_id=task.context.tenant_id,
                request_id=str(task.context.current_state.get("request_id") or task.case_id),
                action_type=ACTION_TYPE, business_subject=f"{trip['trip_id']}:v{trip['version']}"),
            approval_required=False, risk_level="low", rationale_evidence_ids=[])
        return work._result(task, outcome="completed", confidence=0.9, evidence=evidence, answer=answer,
                            next_action=NextAction.RESPOND, action_proposals=[proposal], warnings=warnings,
                            decisions=[{"itinerary": "batch", "items": len(outcomes), **summary,
                                        "execution_plan": self.plan.evidence(),
                                        "timing": {"total_seconds": round(sum(o.seconds for o in outcomes), 3),
                                                   "total_calls": sum(o.calls for o in outcomes),
                                                   "items": [{"item": o.item.title, "kind": o.kind, "seconds": o.seconds, "calls": o.calls}
                                                             for o in outcomes if o.calls or o.seconds]}}])

    def _arguments(self, trip: dict[str, Any], base: int, outcomes: list[Outcome], applied: list[Outcome],
                   asked: list[Outcome], consent: list[Outcome], stuck: list[Outcome],
                   retry: list[Outcome]) -> tuple[dict[str, Any], str]:
        """제안 인자 — `replacements`(판에 넣을 것 + 묻는 것의 안), `batch`(항목별 원인 · 묻기 · 다시 열 항목), `notice`(판이 바뀔 때의 알림), `guidance`(판이 안 바뀔 때 안 바꾼 것을 알리는 알림)."""
        replacements = {old: new for o in [*applied, *asked] for old, new in o.change.replacements.items()}
        # ★새 판의 원인 기록은 **실제로 바꾼 항목의 원인**만 — 묻기만 한 · 못 푼 항목의 원인이 「왜 바뀌었나」에 섞이지 않게(계획서 링크가 읽는다)
        version_causes = [cause for o in applied for cause in o.causes]
        change = ItineraryChange(
            reason="auto_adjusted", causes=version_causes, notice=digest(outcomes, kind="change_notice") if applied else {"text": ""},
            replacements=replacements, summary={"batch": True, "applied": [o.item.title for o in applied],
                                                "execution_plan": self.plan.evidence()})
        arguments = change_arguments(trip_id=trip["trip_id"], base_version=base, change=change)
        arguments["batch"] = {
            "causes": {str(o.item.item_id): o.causes for o in outcomes if o.kind in ("applied", "asked", "consent")},
            "consents": [{"item_id": str(o.item.item_id), "causes": o.causes, "indoor_unknown": o.indoor_unknown} for o in consent],
            "applied": [str(o.item.item_id) for o in applied],
            # ★다시 열 항목 — 적용기가 요약에 옮기고(`applied_actions[].summary.batch.retry`) 감시가 그 항목의 덮음을 풀어 준다
            "retry": [str(o.item.item_id) for o in retry]}
        if not applied:
            arguments["guidance"] = digest(outcomes, kind="guidance") if stuck or retry else None
        # 판이 안 바뀌고 안 바꾼 것도 없으면(묻기만 했다) 묻는 줄을 그대로 답으로 — 따로 여쭤본 것이 무엇인지 Case 에 남는다
        answer = (arguments["notice"]["text"] if applied
                  else (arguments["guidance"]["text"] if arguments.get("guidance") else digest(outcomes, kind="change_notice")["text"]))
        return arguments, answer


__all__ = ["WATCH_KINDS", "Outcome", "WatchBatch", "digest", "guidance_key"]
