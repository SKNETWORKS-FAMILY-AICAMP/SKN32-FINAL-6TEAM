# -*- coding: utf-8 -*-
"""Case 버전의 **감시 루프** — 곧 시작할 항목을 점검하고, 깨졌으면 **Case 를 연다.**

★v11 §6-A ① 그대로다 — 「되잡기 작업은 Case 를 만들기만 한다. 판정도 재계획도 하지 않는다 —
  그건 기존 경로(분류 → Team → 재검증)가 이미 하는 일이다.」

    시나리오용 여행 버전(`trip_watch.py`)   점검 → 대안 계산 → 새 버전을 **직접** 쓴다
    Case 버전(이 파일)                      점검 → **시스템 Case** → Controller → Team → 코어가 적용

★여기서 하는 판정은 「**변화가 있나**」뿐이다(§6-A 3a). 무엇으로 바꿀지는 Team 이 정한다 —
  Team 은 같은 점검을 도구로 **다시** 읽는다(열고 도는 사이에 풀렸을 수 있다).

★시스템 Case 는 무엇이 문제인지 **이미 안다** — LLM 분류를 부르지 않고 라벨을 준다
  (`case_intake.open_case(labels=…)`). 사람이 쓴 글이 아니라 추측할 것이 없다.

★같은 원인으로 두 번 열지 않는다. 요청 id 가 「여행 · 항목 · 원인 지문」이다 — 다음 틱에
  같은 사건이 남아 있어도 같은 Case 로 모인다. 고친 뒤에는 항목 id 가 바뀌므로 새 항목이
  또 깨지면 새 Case 가 열린다(맞는 동작이다).

★`fatal`(결정 15 — 대체 소스까지 실패)·`unhandled`(식사·활동·이동 밖의 항목)·
  `unchecked`(경로 소스가 답할 수 없는 대상)는 시나리오 버전과 같게 **센다.**

★`[2026-10-02 결함 인계 #1·#2·#3]` 이 반복이 **멈추지 않고 끝을 맺게** 한다.
  ① Case 하나의 실행이 예외로 터져도 **그 회차의 나머지 Case 는 계속 돈다** — 터진 Case 는 `escalated`(`team_error`)로 닫아 운영자가 오류로 본다(죽은 채
     `running` 으로 남지 않는다)
  ② 무응답 제안 만료(`PendingStore.expire`)를 이 반복도 한다 — 전에는 시나리오 버전(`trip_watch`)만 불러서, 기본 일꾼(Case 버전)이 도는 동안 끝난 일정의
     제안이 `open` 으로 남았다
  ③ 바꿀 곳을 못 찾아 Team 이 `itinerary_unresolved` 로 끝나면 **고객에게 알린다**(`pending.unresolved_notice` — 일정은 그대로 두었다는 것과 원인). 사람 대기 약속은 없다
  ④ 일시 실패(`fatal_source_failure` 점검 소스 · `team_error` 실행 예외)로 닫힌 Case 는 **다음 회차가 다시 연다** — 같은 지문의 닫힌 Case 가 영원히 막지 않게
     (`retry_max` 번까지 · 사이를 `retry_cooldown_seconds` 이상 두고). 이 실패는 고객에게 알리지 않는다(바뀐 것이 있는지 모른다 — 운영자 몫)

★`[2026-10-03 사용자 지시]` **같은 여행의 문제는 Case 하나로 묶는다**(`trip_watch_batch`). 한 회차에 한 여행의 항목이 둘 이상 깨졌으면(새로 열 것이 둘 이상) 항목마다 Case 를 열지 않고
  **묶음 Case 하나**를 연다 — 한 초안 위에서 차례로 고쳐 판 하나 · 알림 하나. 하나뿐이면 전과 똑같이 그 항목의 Case 다.
  ★항목의 **정체**는 전과 같은 `watch:{여행}:{항목}:{원인 지문}`(`base_id`)이다 — 묶음 Case 는 그 목록을 트리거(`batch`)에 싣고, 다음 회차는 **단일 Case 든 묶음 Case 든** 그 정체를 덮은 Case 가 있으면
  다시 열지 않는다(못 푼 항목이 다음 회차에 다른 묶음으로 다시 열려 3분마다 같은 알림이 나가는 것을 막는다). 일시 실패로 닫힌 묶음 Case 의 항목은 단일 Case 와 같은 규칙으로 다시 열린다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from app.application.case_intake import open_case

from .itinerary import Item, TripStore
from .itinerary_actions import RECHECK_FAILED
from .itinerary_changes import planned_option, route_of, route_targets
from .pending import PendingStore, cause_fingerprint, unresolved_notice
from .replan import WEATHER_LIKE
from .subjects import KIND, resolve_subject

logger = logging.getLogger(__name__)

DEFAULT_LOOKAHEAD = timedelta(minutes=90)
ACTOR = "trip_watch"
#: 다음 회차가 **다시 열어도 되는** 닫힘 사유 — 일시적이다(점검 소스 실패 · 실행 예외). 바꿀 곳이 없음(`itinerary_unresolved`)은 아니다 — 같은 사건이 그대로면 같은 답이다
#: ★`[2026-10-03]` `action_target_changed`(Team 이 계산하는 사이 일정 판이 움직였다 — 낡은 기준이라 적용기가 거절) · `team_timeout_seconds`(묶음은 항목이 많아 Team 시간 제한에 걸릴 수 있다)를 더했다.
#:  둘 다 **같은 사건이 그대로면 다음 회차에 새 기준으로 다시 계산하면 되는** 일시 실패다 — 전에는 같은 지문의 닫힌 Case 가 영원히 막았다(고객이 일정을 만지는 순간 그 항목의 감시가 멈췄다)
RETRYABLE_GUARDRAILS = frozenset({"fatal_source_failure", "team_error", "action_target_changed", "team_timeout_seconds"})


@dataclass
class CaseTickResult:
    checked: int = 0
    opened: list[dict[str, Any]] = field(default_factory=list)
    existing: list[dict[str, Any]] = field(default_factory=list)
    ran: list[dict[str, Any]] = field(default_factory=list)
    fatal: list[dict[str, Any]] = field(default_factory=list)
    unhandled: list[dict[str, Any]] = field(default_factory=list)
    pinned: list[dict[str, Any]] = field(default_factory=list)
    unchecked: list[dict[str, Any]] = field(default_factory=list)
    #: 무응답으로 닫은 제안(끝난 일정) · 실행이 예외로 터진 Case · 다시 연 Case · 바꿀 곳이 없다고 고객에게 알린 건
    expired: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    retried: list[dict[str, Any]] = field(default_factory=list)
    notified: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Issue:
    """이번 회차에 찾은 문제 하나 — 아직 Case 로 안 열었다(여행별로 모아 한 번에 정한다)."""

    trip_id: UUID
    item: Item
    causes: list[dict[str, Any]]
    issue_code: str
    detected: str

    @property
    def base_id(self) -> str:
        return f"watch:{self.trip_id}:{self.item.item_id}:{_fingerprint(self.causes)}"

    def record(self) -> dict[str, Any]:
        return {"trip_id": str(self.trip_id), "item": self.item.title, "issue_code": self.issue_code}


_fingerprint = cause_fingerprint


class TripWatchCaseOpener:
    def __init__(self, *, store: TripStore, check: Callable[..., dict[str, Any]],
                 connection_factory: Callable[[], Any], clock: Callable[[], datetime],
                 repository: Any, run_case: Callable[..., Any] | None,
                 route_events: Any = None, routes: dict[str, Any] | None = None) -> None:
        self.store, self.check = store, check
        self._connect, self.clock = connection_factory, clock
        self.repository, self.run_case = repository, run_case
        self.route_events, self.routes = route_events, routes or {}

    def tick(self, lookahead: timedelta = DEFAULT_LOOKAHEAD) -> CaseTickResult:
        result = CaseTickResult()
        now = self.clock()
        # ★무응답 — 그 일정이 끝난 제안은 닫는다. **바꾸지 않는다**(D-020). 기본 일꾼이 Case 버전이라 여기서도 해야 한다
        with self._connect() as conn, conn.transaction():
            result.expired = [{k: str(v) for k, v in row.items()}
                              for row in PendingStore(self.store.tenant_id).expire(conn, now=now)]
        with self._connect() as conn:
            due = self.store.due(conn, start=now, end=now + lookahead)
        opened: list[UUID] = []
        self._contexts: dict[UUID, dict[str, Any]] = {}
        issues: list[Issue] = []
        for trip_id, item in due:
            if item.detail.get("customer_pinned"):
                # ★`[2026-10-03 사용자 결정 — D-020]` 고정(「변경 안 할 일정」)은 **자동으로 바꾸지 않는다**는 뜻이지 점검에서 빼라는 뜻이 아니다 — 사용자 말:
                #   「안 바꿔도 알림은 받게 해야 함. 바꾸지 않는 것과 알림을 끄는 것은 별개.」 전에는 여기서 `continue` 해 고정한 일정에는 재난문자 · 휴무 같은 위험 알림이
                #   안 나갔다(시나리오 버전 `trip_watch` 는 이미 점검하고 물었다 — 두 감시가 갈려 있었다). 이제 **점검하고 Case 를 연다** — 일정은 적용기가 「변경 안 할 일정이면
                #   먼저 묻는다」(`itinerary_actions._ask_instead`)로 막고(대안이 있으면 안 1·2·3 과 함께, 없으면 `itinerary_unresolved` 알림), 안전 사건이면 안전 알림이다.
                #   `result.pinned` 는 이제 「고정이라 **바꾸지 않고 알린** 항목」을 센다(건너뛴 것이 아니다).
                result.pinned.append({"trip_id": str(trip_id), "item": item.title})
            if item.kind == "mobility":
                result.checked += 1
                self._route(trip_id, item, now, result, issues)
                continue
            if item.place is None:
                continue
            result.checked += 1
            report = self.check(place=item.place, starts_at=item.starts_at)
            verdict = report.get("verdict")
            if verdict == "clear":
                continue
            entry = {"trip_id": str(trip_id), "item": item.title, "report": report}
            if verdict == "fatal":
                result.fatal.append(entry)
                continue
            causes = report.get("disruptions", [])
            if item.kind == "dining":
                # ★`[2026-09-29]` 식사 항목도 연다 — 식당 Team 이 다시 점검하고 근처 식당으로 바꾼다(`handle_trigger`).
                #   ☆전에는 `unhandled` 로 세기만 해서, 같은 재난문자에 걸린 활동은 바뀌고 옆 식당은 그대로였다.
                issues.append(Issue(trip_id, item, causes, "dining_other", "place"))
                continue
            if item.kind != "activity":
                result.unhandled.append(entry)
                continue
            weather = any(cause.get("category") in WEATHER_LIKE for cause in causes)
            issues.append(Issue(trip_id, item, causes, "activity_weather_risk" if weather else "activity_other", "place"))
        self._open_issues(issues, now, result, opened)
        # ★Case 를 다 연 **뒤에** 돌린다 — 커넥션을 잡은 채 Team 을 기다리지 않는다.
        if self.run_case is not None:
            for case_id in opened:
                try:
                    outcome = self.run_case(tenant_id=self.store.tenant_id, case_id=case_id, actor_id=ACTOR)
                except Exception as exc:                  # noqa: BLE001 — 한 Case 의 실패가 이 회차의 나머지를 끊지 않는다
                    logger.exception("watch: run_case failed case=%s", case_id)
                    result.failed.append({"case_id": str(case_id), "error": type(exc).__name__})
                    self._close_failed(case_id, exc)
                    continue
                result.ran.append({"case_id": str(case_id), "status": (outcome or {}).get("status")})
                self._after_run(case_id, outcome, result)
        return result

    # ── 실행 뒤 ───────────────────────────────────────────────
    def _close_failed(self, case_id: UUID, exc: BaseException) -> None:
        """예외로 터진 Case — **죽은 채 `running` 으로 남기지 않고** `escalated`(`team_error`)로 닫는다. 운영자가 오류로 본다.
        (Controller 는 예외가 나면 그 실행 기록만 실패로 닫고 Case 는 그대로 둔다 — 다시 실행되지도, 사람 눈에 띄지도 않았다.)"""
        from app.core.transition import transition_case
        from app.domain.events import CaseStatus, EventType

        try:
            with self._connect() as conn, conn.transaction():
                case = self.repository.get_case(conn, tenant_id=self.store.tenant_id, case_id=case_id)
                if case is None or str(case["status"]) != CaseStatus.RUNNING.value:
                    return                               # 이미 다른 상태로 갔다 — 건드리지 않는다
                transition_case(conn, tenant_id=self.store.tenant_id, case_id=case_id, expected_version=case["version"],
                                event_type=EventType.GUARDRAIL_ESCALATED,
                                payload={"guardrail": "team_error", "observed": [type(exc).__name__]},
                                actor_type="system", actor_id=ACTOR)
        except Exception:                                # noqa: BLE001 — 닫지 못해도 반복은 계속된다. 이유는 남긴다
            logger.exception("watch: could not close the failed case=%s", case_id)

    def _escalation(self, case_id: UUID) -> tuple[str | None, str]:
        """(닫힌 사유 `guardrail`, 관찰 문구 `observed`). 닫힌 적이 없으면 (None, "")."""
        with self._connect() as conn:
            events = self.repository.get_case_events(conn, tenant_id=self.store.tenant_id, case_id=case_id)
        for event in reversed(events):
            if event["event_type"] == "guardrail_escalated":
                payload = event["payload_json"] or {}
                observed = payload.get("observed")
                text = " ".join(str(o) for o in observed) if isinstance(observed, list) else str(observed or "")
                return (str(payload.get("guardrail") or "") or None), text
        return None, ""

    def _after_run(self, case_id: UUID, outcome: dict[str, Any] | None, result: CaseTickResult) -> None:
        """Team 이 `itinerary_unresolved`(바꿀 곳 없음)로 끝났으면 **고객에게 알린다** — 일정은 그대로라는 것과 원인."""
        context = self._contexts.get(case_id)
        if context is None or (outcome or {}).get("status") != "escalated":
            return
        if "batch" in context:
            return self._after_batch(case_id, context, result)
        guardrail, observed = self._escalation(case_id)
        # ★바꿀 곳이 없어서(`itinerary_unresolved`) 또는 **바꿀 곳은 찾았는데 일정 전체 재판정이 막아서**(`action_rejected` + 머리가 `RECHECK_FAILED`). 다른 `action_rejected`(인자 오류 등)는
        #   운영자 몫이라 고객에게 알리지 않는다
        # ★`[2026-10-03]` Team 이 다음 순위 안까지 다 시험해 걸렸으면(`itinerary_recheck_failed`) 적용기에 닿기 전에 끝난다 — 같은 문장으로 알린다
        recheck_failed = (guardrail == "itinerary_recheck_failed"
                          or (guardrail == "action_rejected" and observed.startswith(RECHECK_FAILED)))
        if guardrail != "itinerary_unresolved" and not recheck_failed:
            return
        item, causes = context["item"], context["causes"]
        with self._connect() as conn, conn.transaction():
            self.store.enqueue_message(conn, trip_id=context["trip_id"],
                                       key=f"watch-unresolved:{item.item_id}:{_fingerprint(causes)}",
                                       payload=unresolved_notice(item=item, causes=causes, recheck_failed=recheck_failed))
        result.notified.append({"case_id": str(case_id), "trip_id": str(context["trip_id"]), "item": item.title})

    def _route(self, trip_id: UUID, item: Item, now: datetime, result: CaseTickResult,
               issues: list[Issue]) -> None:
        route = route_of(item, self.routes)
        if not route or self.route_events is None:
            return
        _, planned = planned_option(item, route)
        events = self.route_events.affecting(route_targets(route))
        if events is None:
            result.fatal.append({"trip_id": str(trip_id), "item": item.title,
                                 "report": {"verdict": "fatal", "failed_categories": ["route_events"]}})
            return
        unsupported = getattr(self.route_events, "unsupported", None)
        blind = unsupported(planned.get("uses", [])) if callable(unsupported) else []
        if blind:
            result.unchecked.append({"trip_id": str(trip_id), "item": item.title, "targets": blind})
        hit = [target for target in planned.get("uses", []) if target in events]
        if not hit:
            return
        causes = [{"category": "route_event", "target": target, **events[target]} for target in hit]
        issues.append(Issue(trip_id, item, causes, "mobility_missed_or_disrupted", "route"))

    # ── 여행별로 모아 연다 ───────────────────────────────────────
    def _open_issues(self, issues: list[Issue], now: datetime, result: CaseTickResult, opened: list[UUID]) -> None:
        """찾은 문제를 **여행별로** 모아 연다. 새로 열 것(덮은 Case 가 없거나 일시 실패로 다시 열 만한 것)이 둘 이상이면 묶음 Case 하나, 아니면 전처럼 항목마다."""
        from app.core.settings import get_guardrails

        by_trip: dict[UUID, list[Issue]] = {}
        for issue in issues:
            by_trip.setdefault(issue.trip_id, []).append(issue)
        guard = get_guardrails()
        batching = bool(guard.get("travel.watch.batch_enabled"))
        cap = max(2, int(guard.get("travel.watch.batch_max_items")))
        for trip_id, group in by_trip.items():
            fresh: list[tuple[Issue, int]] = []
            with self._connect() as conn:
                for issue in group:
                    attempt, covered_by = self._attempt(conn, issue.base_id, issue.item.item_id)
                    if attempt is None:
                        result.existing.append({**issue.record(), "case_id": str(covered_by)})
                    else:
                        fresh.append((issue, attempt))
            if not batching or len(fresh) < 2:
                for issue, attempt in fresh:
                    self._open_single(issue, attempt, now, result, opened)
                continue
            for at in range(0, len(fresh), cap):
                chunk = fresh[at:at + cap]
                if len(chunk) < 2:
                    self._open_single(*chunk[0], now, result, opened)
                else:
                    self._open_batch(trip_id, chunk, now, result, opened)

    def _attempt(self, conn: Any, base_id: str, item_id: UUID) -> tuple[int | None, str | None]:
        """(몇 번째 시도인가, 덮은 Case). 이 문제(`base_id`)를 **덮은 Case** 가 단일이든 묶음이든 없으면 (0, None) — 새로 연다.
        있는데 **다시 열 만하면**(일시 실패로 닫혔다 · 묶음이 이 항목을 「다시 열 항목」으로 남겼다) 한도 안이고 식힘 시간이 지났을 때 (몇 번째 재시도, …) — 다시 연다.
        아니면 (None, 덮은 Case) — 열지 않는다(같은 사건에 두 번 안 연다).

        ★`[2026-10-03 적대 검토]` 묶음 Case 는 **끝난 상태가 구성원 전체의 상태가 아니다** — 하나가 `resolved` 여도 그 안의 점검 소스 실패 · 예외 · 시간 초과 항목은 아무도 풀지 않았다.
        그래서 항목마다 본다: 완료된 묶음은 적용 요약의 `batch.retry`, 못 바꾸고 닫힌 묶음은 닫힘 표지 `retry:{항목}` 이 그 항목을 가리키면 다시 열린다."""
        from app.core.settings import get_guardrails

        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.case_id, c.status, extract(epoch FROM (now() - c.updated_at)), "
                "       (SELECT e.payload_json->>'guardrail' FROM case_events e "
                "         WHERE e.tenant_id=c.tenant_id AND e.case_id=c.case_id AND e.event_type='guardrail_escalated' "
                "         ORDER BY e.aggregate_version DESC LIMIT 1), "
                "       count(*) OVER (), "
                "       (c.state_json->'trigger' ? 'batch'), "
                "       COALESCE(c.state_json->'applied_actions'->0->'summary'->'batch'->'retry', '[]'::jsonb), "
                "       COALESCE((SELECT e.payload_json->'observed' FROM case_events e "
                "         WHERE e.tenant_id=c.tenant_id AND e.case_id=c.case_id AND e.event_type='guardrail_escalated' "
                "         ORDER BY e.aggregate_version DESC LIMIT 1), '[]'::jsonb) "
                "FROM customer_cases c WHERE c.tenant_id=%s "
                "AND (c.state_json->>'request_id' = %s OR c.state_json->>'request_id' LIKE %s "
                "     OR c.state_json->'trigger'->'batch' @> %s::jsonb) "
                "ORDER BY c.created_at DESC LIMIT 1",
                (self.store.tenant_id, base_id, f"{base_id}:r%", json.dumps([{"base_id": base_id}])))
            row = cur.fetchone()
        if row is None:
            return 0, None
        case_id, status, quiet, guardrail, total = row[0], row[1], float(row[2]), row[3], int(row[4])
        is_batch, retry_ids, observed = bool(row[5]), [str(x) for x in (row[6] or [])], " ".join(str(x) for x in (row[7] or []))
        marked = is_batch and (str(item_id) in retry_ids or f"retry:{item_id}" in observed)
        guard = get_guardrails()
        eligible = (((str(status) == "escalated" and guardrail in RETRYABLE_GUARDRAILS) or marked)
                    and total <= int(guard.get("travel.watch.retry_max"))
                    and quiet >= float(guard.get("travel.watch.retry_cooldown_seconds")))
        return (total, None) if eligible else (None, str(case_id))

    def _open_single(self, issue: Issue, attempt: int, now: datetime, result: CaseTickResult, opened: list[UUID]) -> None:
        item, causes = issue.item, issue.causes
        summary = ", ".join(sorted({str(c.get("kind") or c.get("category")) for c in causes})) or issue.detected
        request_id = issue.base_id if attempt == 0 else f"{issue.base_id}:r{attempt}"
        with self._connect() as conn:
            trip, _ = self.store.latest(conn, issue.trip_id)
            case = open_case(
                conn, repository=self.repository, tenant_id=self.store.tenant_id,
                customer_id=trip["customer_id"], request_id=request_id,
                message=f"[감시] {item.title} — {summary}", channel="system",
                actor_type="system", actor_id=ACTOR,
                subject_ref={"kind": KIND, "id": str(issue.trip_id), "part_id": str(item.item_id)},
                subject_resolver=resolve_subject, trigger_source="schedule",
                trigger={"item_id": str(item.item_id), "at": now.isoformat(), "detected": issue.detected,
                         "categories": sorted({str(c.get("category")) for c in causes})},
                labels={"intent": "incident_report", "issue_code": issue.issue_code, "sentiment": "neutral"})
        record = {**issue.record(), "case_id": str(case.case_id)}
        if case.created:
            opened.append(case.case_id)
            result.opened.append(record)
            if attempt:
                result.retried.append({**record, "attempt": attempt})
            self._contexts[case.case_id] = {"trip_id": issue.trip_id, "item": item, "causes": causes}
        else:
            result.existing.append(record)

    def _open_batch(self, trip_id: UUID, chunk: list[tuple[Issue, int]], now: datetime, result: CaseTickResult,
                    opened: list[UUID]) -> None:
        """한 여행의 문제 둘 이상 — **묶음 Case 하나**. 라벨은 활동(`activity_other`)이다 — 활동 Team 이 조정자다(`trip_watch_batch`).
        요청 id 는 묶음 구성원의 정체(`base_id`) 목록의 지문 — 같은 묶음을 두 번 안 열고, 일시 실패로 닫혔으면 `:r{n}` 으로 다시 연다."""
        issues = [issue for issue, _ in chunk]
        members = sorted(issue.base_id for issue in issues)
        batch_base = f"watch:{trip_id}:batch:" + hashlib.sha1(json.dumps(members).encode("utf-8")).hexdigest()[:12]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s "
                            "AND (state_json->>'request_id' = %s OR state_json->>'request_id' LIKE %s)",
                            (self.store.tenant_id, batch_base, f"{batch_base}:r%"))
                tries = int(cur.fetchone()[0])
            request_id = batch_base if tries == 0 else f"{batch_base}:r{tries}"
            trip, _ = self.store.latest(conn, trip_id)
            titles = ", ".join(i.item.title for i in issues[:3]) + (f" 외 {len(issues) - 3}건" if len(issues) > 3 else "")
            case = open_case(
                conn, repository=self.repository, tenant_id=self.store.tenant_id,
                customer_id=trip["customer_id"], request_id=request_id,
                message=f"[감시] {len(issues)}건이 겹침 — {titles}", channel="system",
                actor_type="system", actor_id=ACTOR,
                subject_ref={"kind": KIND, "id": str(trip_id)},
                subject_resolver=resolve_subject, trigger_source="schedule",
                trigger={"batch": [{"item_id": str(i.item.item_id), "base_id": i.base_id, "detected": i.detected,
                                    "issue_code": i.issue_code,
                                    "categories": sorted({str(c.get("category")) for c in i.causes})} for i in issues],
                         "at": now.isoformat(), "detected": "batch",
                         "categories": sorted({str(c.get("category")) for i in issues for c in i.causes})},
                labels={"intent": "incident_report", "issue_code": "activity_other", "sentiment": "neutral"})
        record = {"trip_id": str(trip_id), "item": titles, "case_id": str(case.case_id), "issue_code": "batch",
                  "items": [i.item.title for i in issues]}
        if case.created:
            opened.append(case.case_id)
            result.opened.append(record)
            retried = max((attempt for _, attempt in chunk), default=0)
            if tries or retried:
                result.retried.append({**record, "attempt": max(tries, retried)})
            self._contexts[case.case_id] = {"trip_id": trip_id, "batch": issues}
        else:
            result.existing.append(record)

    def _after_batch(self, case_id: UUID, context: dict[str, Any], result: CaseTickResult) -> None:
        """묶음 Case 가 **아무것도 못 바꾸고** 끝났다 — Team 이 남긴 항목별 표지(`outcome:{항목}:{결과}`)로 못 푼 항목을 고객에게 **한 번에** 알린다.
        표지가 없으면(점검 소스 실패 · 예외) 알리지 않는다 — 바뀐 것이 있는지 모른다(운영자 몫)."""
        from .trip_watch_batch import Outcome, digest, guidance_key

        guardrail, observed = self._escalation(case_id)
        issues = {str(i.item.item_id): i for i in context["batch"]}
        if guardrail == "action_rejected" and observed.startswith(RECHECK_FAILED):
            # ★`[2026-10-03 적대 검토]` Team 이 낸 묶음을 적용기가 일정 전체 재판정으로 **거절**했다 — 단일 Case 처럼 고객에게 알린다(구성원 전원이 「그대로 두었어요」). 안 알리면 구성원 전부가 말없이 막힌다
            found = [(item_id, "recheck_failed") for item_id in issues]
        else:
            found = [(match.group(1), match.group(2))
                     for match in re.finditer(r"outcome:([0-9a-fA-F-]{36}):(no_alternate|recheck_failed)", observed)]
        outcomes = [Outcome(issues[item_id].item, kind, causes=issues[item_id].causes) for item_id, kind in found if item_id in issues]
        if not outcomes:
            return
        payload = digest(outcomes, kind="guidance")
        with self._connect() as conn, conn.transaction():
            self.store.enqueue_message(conn, trip_id=context["trip_id"], key=f"watch-unresolved:batch:{guidance_key(payload)}", payload=payload)
        result.notified.append({"case_id": str(case_id), "trip_id": str(context["trip_id"]),
                                "item": ", ".join(o.item.title for o in outcomes)})


__all__ = ["CaseTickResult", "DEFAULT_LOOKAHEAD", "RETRYABLE_GUARDRAILS", "TripWatchCaseOpener"]
