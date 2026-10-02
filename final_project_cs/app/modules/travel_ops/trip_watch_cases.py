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
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from app.application.case_intake import open_case

from .itinerary import Item, TripStore
from .itinerary_actions import RECHECK_FAILED
from .itinerary_changes import planned_option, route_of, route_targets
from .pending import PendingStore, unresolved_notice
from .replan import WEATHER_LIKE
from .subjects import KIND, resolve_subject

logger = logging.getLogger(__name__)

DEFAULT_LOOKAHEAD = timedelta(minutes=90)
ACTOR = "trip_watch"
#: 다음 회차가 **다시 열어도 되는** 닫힘 사유 — 일시적이다(점검 소스 실패 · 실행 예외). 바꿀 곳이 없음(`itinerary_unresolved`)은 아니다 — 같은 사건이 그대로면 같은 답이다
RETRYABLE_GUARDRAILS = frozenset({"fatal_source_failure", "team_error"})


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


def _fingerprint(causes: list[dict[str, Any]]) -> str:
    """원인의 **종류**만으로 지문을 만든다 — 조회 시각 같은 값이 바뀌어도 같은 사건이다."""
    keys = sorted({f"{c.get('category')}:{c.get('kind') or c.get('target') or ''}" for c in causes})
    return hashlib.sha1(json.dumps(keys, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


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
                self._route(trip_id, item, now, result, opened)
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
                self._open(trip_id, item, now, result, opened, causes=causes,
                           issue_code="dining_other", detected="place")
                continue
            if item.kind != "activity":
                result.unhandled.append(entry)
                continue
            weather = any(cause.get("category") in WEATHER_LIKE for cause in causes)
            self._open(trip_id, item, now, result, opened, causes=causes,
                       issue_code="activity_weather_risk" if weather else "activity_other",
                       detected="place")
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
               opened: list[UUID]) -> None:
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
        self._open(trip_id, item, now, result, opened, causes=causes,
                   issue_code="mobility_missed_or_disrupted", detected="route")

    def _open(self, trip_id: UUID, item: Item, now: datetime, result: CaseTickResult,
              opened: list[UUID], *, causes: list[dict[str, Any]], issue_code: str, detected: str) -> None:
        summary = ", ".join(sorted({str(c.get("kind") or c.get("category")) for c in causes})) or detected
        base_id = f"watch:{trip_id}:{item.item_id}:{_fingerprint(causes)}"
        with self._connect() as conn:
            request_id, retry = self._request_id(conn, base_id)
            trip, _ = self.store.latest(conn, trip_id)
            case = open_case(
                conn, repository=self.repository, tenant_id=self.store.tenant_id,
                customer_id=trip["customer_id"], request_id=request_id,
                message=f"[감시] {item.title} — {summary}", channel="system",
                actor_type="system", actor_id=ACTOR,
                subject_ref={"kind": KIND, "id": str(trip_id), "part_id": str(item.item_id)},
                subject_resolver=resolve_subject, trigger_source="schedule",
                trigger={"item_id": str(item.item_id), "at": now.isoformat(), "detected": detected,
                         "categories": sorted({str(c.get("category")) for c in causes})},
                labels={"intent": "incident_report", "issue_code": issue_code, "sentiment": "neutral"})
        record = {"trip_id": str(trip_id), "item": item.title, "case_id": str(case.case_id),
                  "issue_code": issue_code}
        if case.created:
            opened.append(case.case_id)
            result.opened.append(record)
            if retry:
                result.retried.append({**record, "attempt": retry})
            self._contexts[case.case_id] = {"trip_id": trip_id, "item": item, "causes": causes}
        else:
            result.existing.append(record)


    def _request_id(self, conn: Any, base_id: str) -> tuple[str, int]:
        """(요청 id, 몇 번째 재시도인가). 같은 사건(지문)의 앞 Case 가 **일시 실패로 닫혔고** 한도 안이며 식힘 시간이 지났으면 새 Case 를 연다 —
        요청 id 끝에 `:r{n}` 을 붙여 멱등 키가 달라지게. 아니면 앞 Case 의 id 를 그대로 줘서 같은 Case 로 모인다(두 번 열지 않는다)."""
        from app.core.settings import get_guardrails

        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.status, extract(epoch FROM (now() - c.updated_at)), "
                "       (SELECT e.payload_json->>'guardrail' FROM case_events e "
                "         WHERE e.tenant_id=c.tenant_id AND e.case_id=c.case_id AND e.event_type='guardrail_escalated' "
                "         ORDER BY e.aggregate_version DESC LIMIT 1), "
                "       count(*) OVER () "
                "FROM customer_cases c WHERE c.tenant_id=%s "
                "AND (c.state_json->>'request_id' = %s OR c.state_json->>'request_id' LIKE %s) "
                "ORDER BY c.created_at DESC LIMIT 1", (self.store.tenant_id, base_id, f"{base_id}:r%"))
            row = cur.fetchone()
        if row is None:
            return base_id, 0
        status, quiet, guardrail, total = row[0], float(row[1]), row[2], int(row[3])
        latest = base_id if total == 1 else f"{base_id}:r{total - 1}"
        guard = get_guardrails()
        eligible = (str(status) == "escalated" and guardrail in RETRYABLE_GUARDRAILS
                    and total <= int(guard.get("travel.watch.retry_max"))
                    and quiet >= float(guard.get("travel.watch.retry_cooldown_seconds")))
        return (f"{base_id}:r{total}", total) if eligible else (latest, 0)


__all__ = ["CaseTickResult", "DEFAULT_LOOKAHEAD", "RETRYABLE_GUARDRAILS", "TripWatchCaseOpener"]
