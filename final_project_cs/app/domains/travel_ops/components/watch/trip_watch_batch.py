# -*- coding: utf-8 -*-
"""같은 여행의 문제를 **한 초안 위에서 차례로** 고쳐 판 하나 · 알림 하나로 낸다. `[2026-10-03 사용자 지시 · v11 §6-C-1]`

☆왜: 같은 회차에 한 여행의 항목 셋이 깨지면(예: 재난문자 하나가 활동 · 식당 · 이동을 다 걸었다) 전에는 Case 가 셋 열려 **판 셋 · 알림 셋**이 나갔다. 계획서(§6-C-1)는
「여행당 사건 1건 → 활동 → 식당 → 이동 순으로 앞 초안을 다음에 넘긴다 → 전체 재검증 → **새 버전 1번 + 알림 1번**」이었다.

★자리(적대 검토의 결론): **코어(Controller)를 고치지 않는다.** 코어는 일정(`itinerary`) 어휘를 모른다(INV-CS-ARCH-001) — 「초안을 다음 Team 에 넘긴다」는 일정 초안이 무엇인지 알아야 한다.
도메인 어휘를 넣지 않고 코어에서 하려면 Controller 의 Team 연쇄 실행 · 제안 병합을 새로 만들어야 하는데, 그건 Controller 불변식(INV-CS-RT-* 26개)을 건드리는 큰 변경이다.
그래서 **Case 하나(= 여행 하나)**를 만들고(`trip_watch_cases`) 활동 Team 이 조정자가 되어 이 모듈로 세 종류 항목을 한 초안 위에서 계산한다 — 계산은 세 Team 이 이미 하던 함수
(`plan_activity_trigger` · `plan_dining_trigger` · `plan_mobility_trigger`)를 그대로 부르고, **적용은 코어가 Case 완료와 한 트랜잭션으로 한다**(제안 하나 — `itinerary.apply`).
Case 하나가 곧 한 단위라 **크래시 · 재시도 · 멱등이 전과 같다**(적용 전에 죽으면 Case 가 안 닫혀 다시 돈다 — 중간 초안을 DB 에 두지 않는다).

★순서는 활동 → 식당 → 이동(같은 종류는 시작 시각 순). 뒤 항목은 **앞에서 고친 초안 기준**으로 계산한다 — 앞이 고른 곳을 뒤가 또 고르지 않고(`unused_places`), 앞이 이동 항목을 새로 만들었으면 그
이동은 이미 바뀐 것이다(`nothing`). 항목마다 도구 예산을 따로 쓴다(`seen` 을 새로) — 앞 항목이 예산을 다 써서 뒤 항목이 「못 봤다」가 되지 않게. ★그래서 한 Case 의 호출 합이 `max_steps` 를 넘을 수 있다 —
상한은 **시간**이다: Team 코드는 동기라 `asyncio.wait_for` 가 도중에 끊지 못하므로 시작 뒤 `travel.watch.batch_time_ratio`(Team 제한의 몇 %)가 지나면 **새 항목을 시작하지 않고** 남은 것은 `retry` 로 넘긴다.

★항목마다 결과가 갈린다 — **하나를 못 풀어도 나머지는 진행한다**(사용자 결정):
    applied        일정 전체 재판정까지 통과해 이번 판에 넣는다
    asked          「변경 안 할 일정」 · 「먼저 물어봐」 — 바꾸지 않고 안 1·2·3 을 묻는다(**새 판 기준**으로 연다 — 같은 판에 열면 이 판이 곧 낡아 못 고른다). D-020 — 묻기는 묶지 않고 항목마다 따로.
                   묻는 안도 단일 Case 처럼 **일정 전체 재판정을 통과한 안**만 싣는다(`fit_change`) — 겹치는 안을 고르게 두지 않는다
    consent        활동에 날씨 사건만 — 「바꿀까요?」만 묻는다(대체안을 아직 계산하지 않는다)
    no_alternate   대신 갈 곳이 없다 · recheck_failed  찾았지만 일정 전체와 안 맞는다 — **그대로 두고** 알림에 한 줄로 적는다
    source_failed  점검 소스가 대체까지 실패(결정 15) · error  그 항목의 계산이 예외로 터졌다 · retry  이번에 계산하지 못했다(시간 · 마지막 재판정 뒤에도 그대로 남은 이동) —
                   **고객에게 알리지 않고**(바뀐 것이 있는지 모른다) **다시 열 항목**으로 남긴다(`batch.retry` → 적용 요약 · 닫힘 표지 `retry:`). 감시가 그 항목만 다음 회차에 다시 연다
★「이번 판에 넣는 것」은 항목마다 **누적 재판정**(`fit_change` — 앞에서 고친 초안 위에서)을 통과했고, 마지막에 합친 결과를 **한 번 더** 판정한다. 합친 결과가 걸리면 가장 나중 변경부터 하나씩 빼며 통과할 때까지 —
빠진 것은 `recheck_failed` 다(통째로 거절하지 않는다). 적용기의 같은 판정은 마지막 안전망이다.
★알림 하나에 **안전 사건이 앞**이다 — 머리가 「안전 알림」이고 안전 줄이 맨 위다(묻히지 않게). 묻는 것은 따로 간다(제안 id 가 항목마다 있다).

★알려진 한계(적대 검토 2026-10-03): ①활동을 바꾸면 그 옆 이동은 **새로 만들어지는데**(`refresh_moves_around`) 그 새 이동은 구간 사건을 모르고 경로를 고른다 — 새 이동의 사건은 **다음 회차**가
새 항목으로 다시 본다(단일 Case 때부터 같았다). ②묻는 항목이 둘 이상일 때 하나를 고르면 판이 올라가 나머지 제안은 `superseded` 로 닫히고 다시 묻지 않는다(전부터 있던 한계 — 단일 Case 도 같다).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from time import perf_counter       # 항목별 소요 시간 — 위 `time`(마감 시계)과 따로 둔다(시험이 마감 시계만 바꿔 끼울 수 있게)
from dataclasses import dataclass, field
from typing import Any

from app.core.contracts import ActionProposal, NextAction, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.core.settings import get_guardrails

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.actions.itinerary_actions import ACTION_TYPE, change_arguments, introduced_violations
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, NoChange, refresh_moves_around
from app.domains.travel_ops.components.itinerary.itinerary_fit import fit_change
from app.domains.travel_ops.instances._shared.itinerary_team import Consent
from app.domains.travel_ops.components.team_hooks import watch_planners
from app.domains.travel_ops.components.planning.pending import Decision, _cause_text as cause_text, cause_fingerprint, decide, is_safety

logger = logging.getLogger(__name__)

#: 같은 종류 안에서는 시작 시각 순. 활동 → 식당 → 이동 — 앞이 고친 곳 · 새로 만든 이동을 뒤가 기준으로 삼는다(계획서 §6-C-1)
ORDER = {"activity": 0, "dining": 1, "mobility": 2}
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

    @property
    def safety(self) -> bool:
        return is_safety({"disruptions": self.causes})


def _planner(kind: str):
    """항목 종류 → 계산 함수. ★`[2026-10-06]` 세 팀을 직접 부르지 않는다 — 팀이 조립 때 꽂은
    자리에서 받는다(D-CS-013 `components/team_hooks/watch_planners.py`). 그 팀이 조립에 없으면
    `None` 이고, 그 종류의 문제는 처리되지 않는다 — **다른 팀 계산으로 대신하지 않는다.**
    ☆전에는 세 팀 모듈이 `itinerary_team` 을 불러 순환이 생겨 함수 안에서 늦게 불러야 했다."""
    return watch_planners.planner(kind)


# ── 고객에게 보일 문장 ─────────────────────────────────────────

def _head(count: int) -> str:
    return f"일정에 문제가 {_COUNT_WORD.get(count, str(count))} 가지 겹쳐서 이렇게 처리했어요."


def _line(outcome: Outcome) -> str:
    """항목 하나의 한 줄 — 원인에 있는 말만(`cause_text`). 지어낸 대안 · 약속 없음, 사람 대기 약속도 안 한다."""
    title, why = outcome.item.title, cause_text(outcome.causes)
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
        return f"{title} — {why}. 바꿀 곳을 찾았지만 일정 전체와 맞지 않아 **일정은 그대로 두었어요.**"
    return f"{title} — {why}. 대신 갈 수 있는 곳을 찾지 못해 **일정은 그대로 두었어요.**"       # no_alternate


#: 고객에게 말할 결과 — 안 바꿨거나 못 푼 것까지(바꾸지 않는 것과 알림을 끄는 것은 별개다)
_TELL = ("applied", "asked", "consent", "no_alternate", "recheck_failed")
_UNCHANGED = ("no_alternate", "recheck_failed")
#: 고객에게 알리지 않고 **다시 열 항목** — 바뀐 것이 있는지 모르거나 이번에 계산하지 못했다
_RETRY = ("source_failed", "error", "retry")


def digest(outcomes: list[Outcome], *, kind: str) -> dict[str, Any]:
    """묶음의 알림 하나. `kind` — `change_notice`(판이 바뀜) · `guidance`(안 바꿨다). ★안전 사건 줄이 **앞**이고 하나라도 있으면 머리가 안전 알림이다."""
    # ★판이 바뀌면 묻는 항목도 한 줄씩 적는다(한 이야기로 읽히게). 안 바뀌면(`guidance`) 안 바꾼 것만 — 묻는 것은 제안마다 알림이 따로 있다
    told = [o for o in outcomes if o.kind in (_UNCHANGED if kind == "guidance" else _TELL)]
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

    def __init__(self, work: Any, task: TeamTask, ctx: dict[str, Any]) -> None:
        self.work, self.task, self.ctx = work, task, ctx

    # ── 진입 ────────────────────────────────────────────────────
    def run(self) -> TeamResult:
        work, task, ctx = self.work, self.task, self.ctx
        if work.manifest.team_id != "activity":
            # 도구 선언을 합쳐 가진 Team 은 활동뿐이다(`ActivityTeam.manifest.allowed_tools`)
            return work._escalate(task, "batch_not_handled_by_team", ctx["evidence"])
        trip, current = ctx["trip"], list(ctx["items"])
        constraints = trip.get("constraints") or {}
        entries = (task.context.current_state.get("trigger") or {}).get("batch") or []
        wanted = self._ordered(entries, current)
        guard = get_guardrails()
        # ★Team 코드는 동기라 `asyncio.wait_for` 가 도중에 끊지 못한다 — 새 항목을 시작하기 전에 스스로 시간을 본다
        stop_at = time.monotonic() + float(guard.get("reliability.team_timeout_seconds")) * float(guard.get("travel.watch.batch_time_ratio"))

        draft, outcomes = list(current), []
        for original in wanted:
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
        return self._result(trip, current, outcomes)

    @staticmethod
    def _ordered(entries: list[dict[str, Any]], items: list[Item]) -> list[Item]:
        by_id = {str(i.item_id): i for i in items}
        found = [by_id[str(e["item_id"])] for e in entries if str(e.get("item_id")) in by_id]
        return sorted(found, key=lambda i: (ORDER.get(i.kind, 9), i.starts_at, i.seq))

    # ── 항목 하나 ───────────────────────────────────────────────
    def _one(self, item: Item, trip: dict[str, Any], constraints: dict[str, Any]) -> Outcome:
        planner = _planner(item.kind)
        if planner is None:
            return Outcome(item, "nothing", reasons=["unhandled_kind"])
        try:
            plan = planner(self.work, self.task, self.ctx, item)
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
            applied = [o for o in outcomes if o.kind == "applied"]
            if not applied:
                break
            introduced = introduced_violations(trip, current, self._merged(current, applied)[0])
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
        summary = {kind: [o.item.title for o in outcomes if o.kind == kind]
                   for kind in ("applied", "asked", "consent", "no_alternate", "recheck_failed", "source_failed", "error", "retry", "nothing")}
        summary = {kind: titles for kind, titles in summary.items() if titles}
        warnings = [f"다시 열 항목 — {o.item.title}: {o.kind}({', '.join(o.reasons[:2])})" for o in retry]

        if not (applied or asked or consent):
            if stuck or retry:
                # 아무것도 못 바꿨다 — 단일 Case 와 같게 escalate 하고, 항목별 결과를 표지로 남긴다(`outcome:` 못 푼 것 → 감시가 고객에게 한 번에 알린다 · `retry:` 다시 열 것).
                #   다시 열 항목이 있으면 **다시 열 수 있는 사유**(`fatal_source_failure`)로 닫는다 — 그 항목이 영원히 막히지 않게
                code = ("fatal_source_failure" if retry else
                        "itinerary_recheck_failed" if all(o.kind == "recheck_failed" for o in stuck) else "itinerary_unresolved")
                tokens = [*(f"outcome:{o.item.item_id}:{o.kind}" for o in stuck), *(f"retry:{o.item.item_id}" for o in retry)]
                return work._escalate(task, code, evidence, warnings=[*tokens, f"묶음 결과: {summary}"])
            return work.settle(task, ctx, NoChange("clear"))

        arguments, answer = self._arguments(trip, trip["version"], outcomes, applied, asked, consent, stuck, retry)
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
            replacements=replacements, summary={"batch": True, "applied": [o.item.title for o in applied]})
        arguments = change_arguments(trip_id=trip["trip_id"], base_version=base, change=change)
        arguments["batch"] = {
            "causes": {str(o.item.item_id): o.causes for o in outcomes if o.kind in ("applied", "asked", "consent")},
            "consents": [{"item_id": str(o.item.item_id), "causes": o.causes, "indoor_unknown": o.indoor_unknown} for o in consent],
            "applied": [str(o.item.item_id) for o in applied],
            # ★다시 열 항목 — 적용기가 요약에 옮기고(`applied_actions[].summary.batch.retry`) 감시가 그 항목의 덮음을 풀어 준다
            "retry": [str(o.item.item_id) for o in retry]}
        if not applied:
            arguments["guidance"] = digest(outcomes, kind="guidance") if stuck else None
        # 판이 안 바뀌고 안 바꾼 것도 없으면(묻기만 했다) 묻는 줄을 그대로 답으로 — 따로 여쭤본 것이 무엇인지 Case 에 남는다
        answer = (arguments["notice"]["text"] if applied
                  else (arguments["guidance"]["text"] if arguments.get("guidance") else digest(outcomes, kind="change_notice")["text"]))
        return arguments, answer


__all__ = ["ORDER", "Outcome", "WatchBatch", "digest", "guidance_key"]
