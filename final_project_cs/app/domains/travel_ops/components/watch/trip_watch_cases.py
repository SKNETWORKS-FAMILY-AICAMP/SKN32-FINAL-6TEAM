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
  ① Case 하나의 실행이 예외로 터져도 **그 회차의 나머지 Case 는 계속 돈다** — 터진 Case 는 `escalated`(`team_error`)로 닫아 개발자·QA 가 결함으로 본다(죽은 채
     `running` 으로 남지 않는다)
  ② 무응답 제안 만료(`PendingStore.expire`)를 이 반복도 한다 — 전에는 시나리오 버전(`trip_watch`)만 불러서, 기본 일꾼(Case 버전)이 도는 동안 끝난 일정의
     제안이 `open` 으로 남았다
  ③ 바꿀 곳을 못 찾아 Team 이 `itinerary_unresolved` 로 끝나면 **고객에게 알린다**(`pending.unresolved_notice` — 일정은 그대로 두었다는 것과 원인). 사람 대기 약속은 없다
  ④ 일시 실패(`fatal_source_failure` 점검 소스 · `team_error` 실행 예외)로 닫힌 Case 는 **다음 회차가 다시 연다** — 같은 지문의 닫힌 Case 가 영원히 막지 않게
     (`retry_max` 번까지 · 사이를 `retry_cooldown_seconds` 이상 두고). 이 실패는 기존 일정을 유지한다는 안내와 오류 근거를 남긴다

★`[2026-10-03 사용자 지시]` **같은 여행의 문제는 Case 하나로 묶는다**(`trip_watch_batch`). 한 회차에 한 여행의 항목이 둘 이상 깨졌으면(새로 열 것이 둘 이상) 항목마다 Case 를 열지 않고
  **묶음 Case 하나**를 연다 — 한 초안 위에서 차례로 고쳐 판 하나 · 알림 하나. 하나뿐이면 전과 똑같이 그 항목의 Case 다.
  ★항목의 **정체**는 전과 같은 `watch:{여행}:{항목}:{원인 지문}`(`base_id`)이다 — 묶음 Case 는 그 목록을 트리거(`batch`)에 싣고, 다음 회차는 **단일 Case 든 묶음 Case 든** 그 정체를 덮은 Case 가 있으면
  다시 열지 않는다(못 푼 항목이 다음 회차에 다른 묶음으로 다시 열려 3분마다 같은 알림이 나가는 것을 막는다). 일시 실패로 닫힌 묶음 Case 의 항목은 단일 Case 와 같은 규칙으로 다시 열린다.
"""
from __future__ import annotations

from app.core.team_availability import TeamUnavailable

import hashlib
import json
import logging
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.case_intake import open_case
from app.application.case_service import ActiveRunError
from app.domains.travel_ops.components.watch.monitoring import record as record_check

from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.actions.itinerary_actions import RECHECK_FAILED
from app.domains.travel_ops.components.itinerary.itinerary_changes import option_hits, planned_option, route_of, route_targets
from app.domains.travel_ops.components.planning.pending import PendingStore, cause_fingerprint, forecast_attention, unresolved_notice
from app.domains.travel_ops.components.planning.replan import WEATHER_LIKE
from app.domains.travel_ops.components.core_hooks.subjects import KIND, resolve_subject

logger = logging.getLogger(__name__)

DEFAULT_LOOKAHEAD = timedelta(minutes=90)
ACTOR = "trip_watch"
#: 다음 회차가 **다시 열어도 되는** 닫힘 사유 — 일시적이다(점검 소스 실패 · 실행 예외). 바꿀 곳이 없음(`itinerary_unresolved`)은 아니다 — 같은 사건이 그대로면 같은 답이다
#: ★`[2026-10-03]` `action_target_changed`(Team 이 계산하는 사이 일정 판이 움직였다 — 낡은 기준이라 적용기가 거절) · `team_timeout_seconds`(묶음은 항목이 많아 Team 시간 제한에 걸릴 수 있다)를 더했다.
#:  둘 다 **같은 사건이 그대로면 다음 회차에 새 기준으로 다시 계산하면 되는** 일시 실패다 — 전에는 같은 지문의 닫힌 Case 가 영원히 막았다(고객이 일정을 만지는 순간 그 항목의 감시가 멈췄다)
RETRYABLE_GUARDRAILS = frozenset({"fatal_source_failure", "classification_failed", "team_error", "action_target_changed", "team_timeout_seconds"})


def _code(guardrail: str | None) -> str:
    """고객 문장에 싣는 오류 코드 — 닫힘 사유 이름만(내부 관찰 문구는 싣지 않는다). 글자 · 숫자 · 밑줄 · 공백 · 점 · 줄표만 남긴다."""
    return re.sub(r"[^\w .-]", "_", str(guardrail or "escalated"))[:80]


@dataclass
class CaseTickResult:
    checked: int = 0
    unavailable: list[dict[str, Any]] = field(default_factory=list)
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
    #: ★`[2026-10-03]` 대안을 못 찾아 **조건을 푼 안을 물어본** 건(`watch_relaxed`) — 「그대로 두었어요」 알림 대신 제안이 나갔다
    relaxed: list[dict[str, Any]] = field(default_factory=list)


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

# 점검 사건의 공개 사실만 알림으로 옮긴다. 외부 응답·오류 본문은 옮기지 않는다.
_NOTICE_CAUSE_FIELDS = frozenset({
    "category", "kind", "summary", "text", "message", "source", "road", "section", "target",
    "incident_id", "serial", "starts_at", "ends_at", "at", "created_at", "announced_at", "confirmed_at",
    "control_type", "lanes", "magnitude", "distance_m", "distance_km", "location", "intensity",
    "areas", "regions", "value", "limit", "station", "basis", "impact", "mode", "simulation_id",
})
_OBSERVATION_FIELDS = frozenset({"confirmed_at", "distance_m", "distance_km"})
_DEFERRED_CODES = RETRYABLE_GUARDRAILS | frozenset({
    "source_failed", "alternate_verification_failed", "departure_revalidation_failed",
    "TimeoutError", "ConnectionError", "ValueError", "TypeError", "RuntimeError",
    "ReadTimeout", "ConnectTimeout", "HTTPStatusError",
})


def _confirmed_causes(report: dict[str, Any]) -> list[dict[str, Any]]:
    """다른 자료 실패와 독립적으로 확인한 사건을 보존한다. 임의의 중첩 응답은 제외한다."""
    checks = {c.get("category"): c for c in report.get("checks") or [] if isinstance(c, dict)}
    causes = []
    for event in report.get("disruptions") or []:
        if not isinstance(event, dict) or not isinstance(event.get("category"), str):
            continue
        cause = {k: v for k, v in event.items() if k in _NOTICE_CAUSE_FIELDS
                 and (v is None or isinstance(v, (str, int, float, bool))
                      or isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v))}
        check = checks.get(cause["category"], {})
        for name in ("source", "confirmed_at"):
            if not cause.get(name) and isinstance(check.get(name), str):
                cause[name] = check[name]
        causes.append(cause)
    return causes


def _deferred_fingerprint(categories: list[str], code: str, confirmed: list[dict[str, Any]]) -> str:
    """사건과 실패 상태로 구분한다. 같은 사건의 재조회·거리·목록 순서는 새 알림이 아니다."""
    state: list[Any] = [categories, code]
    if confirmed:
        identities = []
        for cause in confirmed:
            identity = {k: sorted(v, key=str) if isinstance(v, list) else v
                        for k, v in cause.items() if k not in _OBSERVATION_FIELDS}
            identities.append(json.dumps(identity, sort_keys=True, ensure_ascii=False, default=str))
        state.append(sorted(set(identities)))
    return hashlib.sha256(json.dumps(state, ensure_ascii=False).encode()).hexdigest()[:16]


def _early_event_key(cause: dict[str, Any]) -> str:
    """조회 시각·거리는 빼고 제공처 사건 정체를 보존한다. 기존 Case 키는 바꾸지 않는다."""
    identity = {key: cause.get(key) for key in ("category", "kind", "source")}
    event = {key: cause[key] for key in ("incident_id", "serial") if cause.get(key)}
    if not event:
        event = {key: cause[key] for key in ("road", "section", "starts_at", "announced_at", "at", "regions", "areas")
                 if cause.get(key) is not None}
        if cause.get("category") == "disaster_msg":
            event["message"] = cause.get("text") or cause.get("message")
    identity["event"] = event
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


class TripWatchCaseOpener:
    def __init__(self, *, store: TripStore, check: Callable[..., dict[str, Any]],
                 connection_factory: Callable[[], Any], clock: Callable[[], datetime],
                 repository: Any, run_case: Callable[..., Any] | None,
                 route_events: Any = None, routes: dict[str, Any] | None = None,
                 departure_observer: Callable[..., dict[str, Any]] | None = None,
                 diagnostic_recorder: Callable[[dict], dict] | None = None,
                 place_status: Any | None = None) -> None:
        self.store, self.check = store, check
        self._connect, self.clock = connection_factory, clock
        self.repository, self.run_case = repository, run_case
        self.route_events, self.routes = route_events, routes or {}
        self.departure_observer = departure_observer
        self.diagnostic_recorder = diagnostic_recorder
        self.place_status = place_status

    def tick(self, lookahead: timedelta = DEFAULT_LOOKAHEAD) -> CaseTickResult:
        result = CaseTickResult()
        now = self.clock()
        # ★무응답 — 그 일정이 끝난 제안은 닫는다. **바꾸지 않는다**(D-020). 기본 일꾼이 Case 버전이라 여기서도 해야 한다
        with self._connect() as conn, conn.transaction():
            result.expired = [{k: str(v) for k, v in row.items()}
                              for row in PendingStore(self.store.tenant_id).expire(conn, now=now)]
        with self._connect() as conn:
            due = self.store.due(conn, start=now, end=now + lookahead)
            if self.departure_observer is not None:
                seen = {(trip_id, item.item_id) for trip_id, item in due}
                due += [(trip_id, item) for trip_id, item in self.store.pending_departures(conn, now=now)
                        if (trip_id, item.item_id) not in seen]
        opened: list[UUID] = []
        self._contexts: dict[UUID, dict[str, Any]] = {}
        issues: list[Issue] = []
        for trip_id, item in due:
            from app.domains.travel_ops.components.conversation.journey_progress import terminal
            if terminal(item) or item.detail.get("origin"):
                continue
            from app.domains.travel_ops.components.watch.trip_watch_batch import skipped_watch
            skipped = skipped_watch(item.kind, trip_id=trip_id, item_id=item.item_id)
            if skipped is not None:
                result.unavailable.append(skipped)
                record_check('schedule', trip_id=trip_id, item_id=item.item_id, target_title=item.title,
                             report=skipped)
                continue
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
                record_check('schedule', trip_id=trip_id, item_id=item.item_id, target_title=item.title,
                             report={'verdict': 'skipped', 'reason': 'no_place'})
                continue
            result.checked += 1
            validated_report = None
            try:
                report = self.check(place=item.place, starts_at=max(item.starts_at, now))
                if not isinstance(report, dict) or report.get("verdict") not in ("clear", "disrupted", "fatal"):
                    raise ValueError("source_contract_invalid")
                # 식당 상태 추가 조회가 실패해도 독립적으로 확인한 6종의 사실은 유지한다.
                # 계약 검증 전 응답은 보존하지 않는다.
                validated_report = deepcopy(report)
                if self.place_status is not None and item.kind == 'dining' and not item.place.get('_watch_simulation'):
                    with self._connect() as conn:
                        trip, _ = self.store.latest(conn, trip_id)
                    status = self.place_status.lookup(tenant=self.store.tenant_id, customer_id=trip['customer_id'],
                                                     trip_id=trip_id, place=item.place, start=item.starts_at,
                                                     end=item.ends_at, now=now, scheduled=True)
                    if status['status'] == 'skipped':
                        result.checked -= 1
                        result.unchecked.append({'trip_id': str(trip_id), 'item': item.title, 'reason': status['reason']})
                        record_check('schedule', trip_id=trip_id, item_id=item.item_id, target_title=item.title, report=status)
                        continue
                    report = self.place_status.merge(report, status)
            except Exception as exc:  # 한 자료 조회의 실패가 다른 항목 점검을 끊지 않는다.
                report = {**(validated_report or {}), "verdict": "fatal",
                          "failed_categories": sorted({*(validated_report or {}).get("failed_categories", []), "place_check"}),
                          "error_code": type(exc).__name__}
            record_check('schedule', trip_id=trip_id, item_id=item.item_id, target_title=item.title, report=report)
            for incomplete in report.get("unverified_checks", []):
                result.unchecked.append({"trip_id": str(trip_id), "item": item.title, **incomplete})
            verdict = report.get("verdict")
            with self._connect() as conn, conn.transaction():
                attention = forecast_attention(conn, store=self.store, trip_id=trip_id, item=item, report=report)
            if attention is not None:
                result.notified.append(attention)
            if verdict == "clear":
                continue
            entry = {"trip_id": str(trip_id), "item": item.title, "report": report}
            if verdict == "fatal":
                result.fatal.append(entry)
                self._defer_notice(trip_id, item, report, now, result)
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
                except TeamUnavailable as exc:
                    from app.core.service_bindings import current_bindings
                    logger.warning("watch_case_team_unavailable team_id=%s reason=%s composition_revision=%s",
                                   exc.team_id, exc.reason, getattr(current_bindings(), "revision", None))
                    entry = {"case_id": str(case_id), "kind": exc.team_id, "reason": exc.reason}
                    result.unavailable.append(entry)
                    if exc.reason in {"engine_unavailable", "composition_unbound"}:
                        result.fatal.append(entry)
                    continue  # Controller가 보존한 상태를 일반 실행 실패로 다시 닫지 않는다.
                except ActiveRunError:
                    # 다른 회차가 먼저 시작했다. 그 활성 업무를 실패로 닫지 않는다.
                    result.existing.append({"case_id": str(case_id), "reason": "active_run"})
                    continue
                except Exception as exc:                  # noqa: BLE001 — 한 Case 의 실패가 이 회차의 나머지를 끊지 않는다
                    logger.exception("watch: run_case failed case=%s", case_id)
                    result.failed.append({"case_id": str(case_id), "error": type(exc).__name__})
                    self._close_failed(case_id, exc)
                    self._after_run(case_id, {"status": "escalated"}, result)
                    continue
                result.ran.append({"case_id": str(case_id), "status": (outcome or {}).get("status")})
                self._after_run(case_id, outcome, result)
        return result

    # ── 실행 뒤 ───────────────────────────────────────────────
    def _defer_notice(self, trip_id, item, report, now, result, *, case_id=None):
        """변경은 보류하되 독립적으로 확인한 사건은 알린다. 같은 사건·실패 상태는 한 번만 저장한다."""
        from app.domains.travel_ops.components.watch.trip_watch_batch import Outcome, digest

        candidate_code = str(report.get("error_code") or "source_failed")
        # 문자 치환만 하면 오류 본문의 비밀도 남는다. 정해진 내부 코드만 노출한다.
        code = candidate_code if candidate_code in _DEFERRED_CODES else "source_failed"
        categories = sorted({str(c) for c in report.get("failed_categories", [])})
        confirmed = _confirmed_causes(report)
        causes = [*confirmed, *({"category": c, "kind": "source_unavailable"} for c in categories)]
        payload = digest([Outcome(item, "source_failed", causes=causes, reasons=[code],
                                  checked_at=now.isoformat())], kind="guidance")
        with self._connect() as conn, conn.transaction():
            trip, _ = self.store.latest(conn, trip_id)
            fingerprint = _deferred_fingerprint(categories, code, confirmed)
            # 같은 장소 · 같은 날의 일정이 바뀌어 id 가 달라져도 같은 미룸 안내를 두 번 보내지 않는다.
            key = f"watch-deferred:{item.place_id or item.item_id}:{item.starts_at.date()}:{fingerprint}"
            added = self.store.enqueue_message(conn, trip_id=trip_id, key=key, payload=payload)
        diagnostic = {"event": "travel_execution_diagnostic", "plan_sha256": None,
                      "tenant_id": str(self.store.tenant_id), "customer_id": str(trip['customer_id']),
                      "trip_id": str(trip_id), "item_id": str(item.item_id),
                      "case_id": str(case_id) if case_id else None,
                      "code": "source_failed", "error_code": code, "checked_at": now.isoformat()}
        collection = report.get('diagnostic')
        if collection is None and self.diagnostic_recorder is not None:
            try:
                collection = self.diagnostic_recorder(diagnostic)
            except Exception:
                collection = {"status": "collection_degraded"}
            if collection.get("status") == "collection_degraded":
                logger.error("travel_diagnostic status=collection_degraded code=source_failed")
        logger.warning("travel_execution_diagnostic", extra={"diagnostic": diagnostic, "collection": collection})
        if added:
            result.notified.append({"trip_id": str(trip_id), "item": item.title, "code": code})

    def _close_failed(self, case_id: UUID, exc: BaseException) -> None:
        """예외로 터진 Case — **죽은 채 `running` 으로 남기지 않고** `escalated`(`team_error`)로 닫는다. 개발자·QA 가 결함으로 본다(상주 운영자는 없다).
        (Controller 는 예외가 나면 그 실행 기록만 실패로 닫고 Case 는 그대로 둔다 — 다시 실행되지도, 결함 기록에 잡히지도 않았다.)"""
        from app.core.transition import transition_case
        from app.core.case_lifecycle.events import CaseStatus, EventType

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
        if guardrail in RETRYABLE_GUARDRAILS:
            self._defer_notice(context["trip_id"], context["item"],
                               {"error_code": guardrail, "failed_categories": ["execution"]},
                               self.clock(), result, case_id=case_id)
            return
        # ★바꿀 곳이 없어서(`itinerary_unresolved`) 또는 **바꿀 곳은 찾았는데 일정 전체 재판정이 막아서**(`action_rejected` + 머리가 `RECHECK_FAILED`).
        # ★`[2026-10-03]` Team 이 다음 순위 안까지 다 시험해 걸렸으면(`itinerary_recheck_failed`) 적용기에 닿기 전에 끝난다 — 같은 문장으로 알린다
        recheck_failed = (guardrail == "itinerary_recheck_failed"
                          or (guardrail == "action_rejected" and observed.startswith(RECHECK_FAILED)))
        if guardrail != "itinerary_unresolved" and not recheck_failed:
            # ★`[2026-10-14]` 그 밖의 실패(인자 오류로 적용기 거절 · 모름 · 제안 검증 실패 · 시간 초과 …)는 다시 시도하지 않는다. 전에는 「운영자 몫」이라
            #   알리지 않았는데 운영자가 없다(D-018 · D-CS-014) — 고객도 모르고 아무도 처리하지 않았다. 일정은 그대로라는 것과 시각 · 코드를 한 번 알린다
            self._unhandled_notice(context["trip_id"], context["item"], context["causes"], guardrail, result, case_id)
            return
        item, causes = context["item"], context["causes"]
        # ★`[2026-10-03 사용자 지적]` 못 찾았다고 곧바로 끝내지 않는다 — 조건을 풀어 **비슷한 안**이 있으면 그것을 묻는다(자동 적용 없음). 한 곳도 없을 때만 아래 옛 알림
        if self._offer_relaxed(context["trip_id"], item, causes, recheck_failed, result, case_id):
            return
        with self._connect() as conn, conn.transaction():
            self.store.enqueue_message(conn, trip_id=context["trip_id"],
                                       key=f"watch-unresolved:{item.item_id}:{_fingerprint(causes)}",
                                       payload=unresolved_notice(item=item, causes=causes, recheck_failed=recheck_failed))
        result.notified.append({"case_id": str(case_id), "trip_id": str(context["trip_id"]), "item": item.title})

    def _unhandled_notice(self, trip_id: UUID, item: Item, causes: list[dict[str, Any]], guardrail: str | None,
                          result: CaseTickResult, case_id: UUID) -> None:
        """다시 시도하지 않는 실패를 고객에게 한 번 알린다 — 같은 항목 · 같은 원인 · 같은 코드면 다시 안 보낸다."""
        from app.domains.travel_ops.components.watch.trip_watch_batch import Outcome, digest

        code = _code(guardrail)
        payload = digest([Outcome(item, "unhandled", causes=causes, reasons=[code], checked_at=self.clock().isoformat())],
                         kind="guidance")
        with self._connect() as conn, conn.transaction():
            added = self.store.enqueue_message(conn, trip_id=trip_id,
                                               key=f"watch-unhandled:{item.item_id}:{_fingerprint(causes)}:{code}",
                                               payload=payload)
        if added:
            result.notified.append({"case_id": str(case_id), "trip_id": str(trip_id), "item": item.title, "code": code})

    def _offer_relaxed(self, trip_id: UUID, item: Item, causes: list[dict[str, Any]], recheck_failed: bool,
                       result: CaseTickResult, case_id: UUID) -> bool:
        """조건을 푼 안을 물었으면 True(옛 알림은 안 낸다). 못 찾았거나 실패했으면 False — 부르는 쪽이 지금처럼 알린다(`watch_relaxed.try_offer` 는 예외를 삼킨다)."""
        from app.domains.travel_ops.components.watch.watch_relaxed import try_offer

        from app.domains.travel_ops.components import candidate_diagnostics

        with candidate_diagnostics.scope(case_id=str(case_id)):
            offered = try_offer(self._connect, store=self.store, trip_id=trip_id, item_id=item.item_id, causes=causes,
                                check=self.check, recheck_failed=recheck_failed)
        if offered is None:
            return False
        if offered.get("status") == "source_failed":
            self._defer_notice(trip_id, item, {"error_code": "alternate_verification_failed",
                                             "failed_categories": offered.get("failed_categories", [])},
                               self.clock(), result, case_id=case_id)
            return True
        result.relaxed.append({"case_id": str(case_id), "trip_id": str(trip_id), "item": item.title,
                               "proposal_id": offered.get("proposal_id"), "already": bool(offered.get("already")),
                               "options": [o["name"] for o in offered["options"]]})
        return True

    def _route(self, trip_id: UUID, item: Item, now: datetime, result: CaseTickResult,
               issues: list[Issue]) -> None:
        if self.departure_observer is not None and item.starts_at <= now:
            self._departure(trip_id, item, now, result, issues)
            return
        route = route_of(item, self.routes)
        if not route or self.route_events is None:
            record_check('mobility', trip_id=trip_id, item_id=item.item_id, target_title=item.title,
                         report={'verdict': 'unchecked', 'reason': 'route_or_source_missing'})
            return
        _, planned = planned_option(item, route)
        try:
            events = self.route_events.affecting(route_targets(route))
        except Exception:  # 조회 오류는 이 구간에만 격리한다.
            events = None
        if events is None:
            record_check('mobility', trip_id=trip_id, item_id=item.item_id, target_title=item.title,
                         report={'verdict': 'fatal', 'failed_categories': ['route_events']})
            result.fatal.append({"trip_id": str(trip_id), "item": item.title,
                                 "report": {"verdict": "fatal", "failed_categories": ["route_events"]}})
            self._defer_notice(trip_id, item, {"failed_categories": ["route_events"]}, now, result)
            return
        unsupported = getattr(self.route_events, "unsupported", None)
        blind = unsupported(planned.get("uses", [])) if callable(unsupported) else []
        if blind:
            result.unchecked.append({"trip_id": str(trip_id), "item": item.title, "targets": blind})
        hit = list(option_hits(planned, events))
        record_check('mobility', trip_id=trip_id, item_id=item.item_id, target_title=item.title,
                     report={'verdict': 'disrupted' if hit else 'unchecked' if blind else 'clear',
                             'targets': blind, 'disruptions': [{'target': target, **events[target]} for target in hit]})
        if not hit:
            return
        causes = [{"category": "route_event", "target": target, **events[target]} for target in hit]
        issues.append(Issue(trip_id, item, causes, "mobility_missed_or_disrupted", "route"))

    def _departure(self, trip_id: UUID, item: Item, now: datetime,
                   result: CaseTickResult, issues: list[Issue]) -> None:
        from app.domains.travel_ops.components.watch.trip_reminders import build_departure

        with self._connect() as conn:
            if self.store.message_exists(conn, trip_id=trip_id, key=f"departure:{item.item_id}"):
                return
            trip, items = self.store.latest(conn, trip_id)
        # 다른 회차의 항목을 최신 일정으로 오인하지 않는다.
        current = next((i for i in items if i.item_id == item.item_id), None)
        following = next((i for i in sorted(items, key=lambda i: i.seq)
                          if i.seq > item.seq and i.kind != "mobility"), None)
        if current is None or following is None or not current.starts_at <= now < following.starts_at:
            return
        observed = []

        def observe(*args, **kwargs):
            got = self.departure_observer(*args, **kwargs)
            observed.append(got)
            return got

        try:
            status, _ = build_departure(current, items, route_events=self.route_events,
                routes=self.routes, now=now, departure_observer=observe, trip=trip)
        except Exception as exc:  # noqa: BLE001 — 다른 이동 점검을 끊지 않고 실패를 센다
            status = "fatal"
            observed.append({"reason": "departure_revalidation_failed", "exception_type": type(exc).__name__})
        observation = observed[-1] if observed and isinstance(observed[-1], dict) else {}
        record_check('departure', trip_id=trip_id, item_id=item.item_id, target_title=current.title,
                     report={'verdict': status, 'observation': observation})
        if status == "fatal":
            result.fatal.append({"trip_id": str(trip_id), "item": current.title,
                "report": {"verdict": "fatal", "failed_categories": ["departure_revalidation"],
                           "observation": observation}})
            self._defer_notice(trip_id, current, {"failed_categories": ["departure_revalidation"],
                "error_code": observation.get("exception_type") or "departure_revalidation_failed"}, now, result)
        elif status == "held":
            reason = observation.get("reason") or ("route_missing" if not route_of(current, self.routes)
                                                    else "route_event")
            causes = [{"category": "departure_revalidation", "kind": reason}]
            issues.append(Issue(trip_id, current, causes, "mobility_missed_or_disrupted", "departure"))
        elif status == "unchecked":
            result.unchecked.append({"trip_id": str(trip_id), "item": current.title,
                                     "targets": "departure_route_events"})

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
            refresh: list[tuple[Issue, str | None]] = []
            with self._connect() as conn:
                for issue in group:
                    attempt, covered_by = self._attempt(conn, issue.base_id, issue.item.item_id)
                    if attempt is None:
                        result.existing.append({**issue.record(), "case_id": str(covered_by)})
                        self._repair_traffic_notice(conn, issue, result)
                        refresh.append((issue, covered_by))
                    elif covered_by is not None:
                        # 실행 실패로 멈춘 동일 사건이다. 새 Case/재시도 지문을 만들지 않는다.
                        self._recover_existing(conn, issue, covered_by, group, result, opened)
                    else:
                        fresh.append((issue, attempt))
            # 기존 연결과 잠금을 모두 닫은 뒤 경고부터 커밋한다. 후보 계산은 이 뒤에도 오래 걸릴 수 있다.
            try:
                self._early_notice(trip_id, group, result)
            except Exception as exc:  # noqa: BLE001 — 선안내 실패가 기존 Case 처리를 막지 않는다
                logger.exception("watch: early risk notice failed")
                result.failed.append({"trip_id": str(trip_id), "reason": "early_notice_failed",
                                      "error_code": type(exc).__name__})
            # 보완 알림의 여행 잠금을 해제한 뒤 별도 연결의 후보 검사·기록을 시작한다.
            for issue, covered_by in refresh:
                self._refresh_existing_alternatives(issue, covered_by, result)
            if not batching or len(fresh) < 2:
                for issue, attempt in fresh:
                    self._open_single(issue, attempt, now, result, opened)
                continue
            for at in range(0, len(fresh), cap):
                chunk = fresh[at:at + cap]
                if len(chunk) < 2:
                    for issue, attempt in chunk:
                        self._open_single(issue, attempt, now, result, opened)
                else:
                    self._open_batch(trip_id, chunk, now, result, opened)

    def _early_notice(self, trip_id: UUID, issues: list[Issue], result: CaseTickResult) -> None:
        """정상 회차의 미안내 위험을 Case 상태와 분리해 대안 계산 전에 커밋한다. 묶음 구성 변화도 항목별로 중복을 거른다."""
        from app.domains.travel_ops.components.planning.pending import _cause_text, is_safety
        from app.domains.travel_ops.components.watch.monitoring import recording

        if not recording() or not issues:
            return
        added = False
        with self._connect() as conn, conn.transaction():
            if not conn.execute("SELECT 1 FROM trips WHERE tenant_id=%s AND trip_id=%s FOR UPDATE",
                                (self.store.tenant_id, trip_id)).fetchone():
                return
            now = self.clock()
            current = {item.item_id: item for current_trip, item in
                       self.store.due(conn, start=now, end=now + DEFAULT_LOOKAHEAD) if current_trip == trip_id}
            fields = ("place_id", "place", "starts_at", "ends_at", "kind", "title", "locked", "booking_id", "detail")
            candidates = {}
            for issue in issues:
                item = current.get(issue.item.item_id)
                if issue.trip_id != trip_id or item is None or any(
                        getattr(item, name) != getattr(issue.item, name) for name in fields):
                    continue
                causes = [cause for cause in _confirmed_causes({"disruptions": issue.causes})
                          if cause.get("kind") != "source_unavailable"]
                for cause in causes:
                    candidates[f"{item.item_id}:{_early_event_key(cause)}"] = (item, [cause])
            if not candidates:
                return
            rows = conn.execute(
                "SELECT payload_json->'risk_fingerprints' FROM outbox WHERE tenant_id=%s AND topic='trip.notice' "
                "AND dedupe_key LIKE %s AND payload_json->'risk_fingerprints' ?| %s::text[]",
                (self.store.tenant_id, str(trip_id) + ':watch-risk-detected:%', list(candidates))).fetchall()
            known = {key for (values,) in rows if isinstance(values, list) for key in values if isinstance(key, str)}
            fresh = {key: value for key, value in candidates.items() if key not in known}
            if not fresh:
                return
            by_item = {}
            for item, item_causes in fresh.values():
                by_item.setdefault(item.item_id, (item, []))[1].extend(item_causes)
            members = [{"item_id": str(item.item_id), "title": item.title, "starts_at": item.starts_at.isoformat(),
                        "ends_at": item.ends_at.isoformat() if item.ends_at else None, "causes": causes}
                       for item, causes in by_item.values()]
            causes = [cause for _, item_causes in by_item.values() for cause in item_causes]
            safety = is_safety({"disruptions": causes})
            zone = ZoneInfo("Asia/Seoul")
            lines = [f"{item.title} ({item.starts_at.astimezone(zone):%m월 %d일 %H:%M}) — {_cause_text(item_causes)}"
                     for item, item_causes in by_item.values()]
            text = ("⚠️ 안전 알림 — " if safety else "일정 주의 안내 — ") + "\n".join(lines)
            text += "\n대안을 확인하고 있어요. 현재 일정은 그대로예요."
            payload = {"type": "safety_alert" if safety else "guidance", "kind": "risk_detected",
                       "text": text, "language": "ko", "causes": causes, "items": members,
                       "risk_fingerprints": sorted(fresh), "checked_at": now.isoformat(), "replay": False}
            if len(members) == 1:
                payload["item_id"] = members[0]["item_id"]
            fingerprint = hashlib.sha256(json.dumps(sorted(fresh)).encode()).hexdigest()[:16]
            added = self.store.enqueue_message(conn, trip_id=trip_id,
                key=f"watch-risk-detected:{fingerprint}", payload=payload)
        # 읽는 이가 저장 전 결과를 성공으로 세지 않도록 커밋 뒤에 기록한다.
        if added:
            result.notified.append({"trip_id": str(trip_id), "item": ", ".join(member["title"] for member in members),
                                    "reason": "risk_detected", "items": [member["item_id"] for member in members]})

    def _refresh_existing_alternatives(self, issue: Issue, case_id: str | None,
                                       result: CaseTickResult) -> None:
        """개선된 실내 검색을 과거 대안 없음 항목에도 한 번 적용한다. 일정은 바꾸지 않는다."""
        from app.domains.travel_ops.components.watch.monitoring import recording
        from app.domains.travel_ops.components.watch.watch_relaxed import enabled

        if not recording() or not enabled() or self.repository is None or not case_id or issue.item.kind != "activity":
            return
        guardrail, _ = self._escalation(UUID(str(case_id)))
        if guardrail not in {"itinerary_unresolved", "itinerary_recheck_failed"}:
            return
        with self._connect() as conn:
            seen = conn.execute(
                "SELECT 1 FROM travel_watch_checks WHERE tenant_id=%s AND trip_id=%s AND item_id=%s "
                "AND stage='alternate_refresh' AND report->>'reason'='indoor_candidates_v3_visit_window' "
                "AND report->>'case_id'=%s AND report->>'status' IN ('asked','no_alternate') LIMIT 1",
                (self.store.tenant_id, issue.trip_id, issue.item.item_id, str(case_id))).fetchone()
            if seen:
                return
            now = self.clock()
            current = next((item for trip_id, item in self.store.due(conn, start=now, end=now + DEFAULT_LOOKAHEAD)
                            if trip_id == issue.trip_id and item.item_id == issue.item.item_id), None)
            fields = ("place_id", "starts_at", "ends_at", "kind", "title", "locked", "booking_id", "detail")
            if current is None or any(getattr(current, name, None) != getattr(issue.item, name, None) for name in fields):
                return
        # 후보 계산과 감시 기록은 별도 연결을 쓰므로 위의 읽기 연결도 먼저 닫는다.
        before = len(result.relaxed)
        handled = self._offer_relaxed(issue.trip_id, current, issue.causes,
                                      guardrail == "itinerary_recheck_failed", result, UUID(str(case_id)))
        status = "asked" if len(result.relaxed) > before else "source_failed" if handled else "no_alternate"
        record_check('alternate_refresh', trip_id=issue.trip_id, item_id=issue.item.item_id,
                     target_title=issue.item.title, report={"reason": "indoor_candidates_v3_visit_window", "case_id": str(case_id), "status": status})

    def _repair_traffic_notice(self, conn: Any, issue: Issue, result: CaseTickResult) -> None:
        """닫힌 사건을 다시 실행하지 않고 기존 알림에서 빠진 현재 도로통제 설명만 보완한다."""
        from app.domains.travel_ops.components.planning.pending import traffic_detail_notice

        if not any(c.get("category") == "traffic_control" for c in issue.causes):
            return
        rows = conn.execute(
            "SELECT payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice' AND status='delivered' "
            "AND dedupe_key LIKE %s AND payload_json->>'item_id'=%s "
            "AND payload_json->>'kind' IN ('no_alternate','recheck_failed') ORDER BY available_at DESC LIMIT 10",
            (self.store.tenant_id, str(issue.trip_id) + ':%', str(issue.item.item_id))).fetchall()
        if not rows:
            return
        with conn.transaction():
            # 최신 일정 저장·여행 정지와 같은 여행 행의 잠금을 공유한다.
            if not conn.execute("SELECT 1 FROM trips WHERE tenant_id=%s AND trip_id=%s FOR UPDATE",
                                (self.store.tenant_id, issue.trip_id)).fetchone():
                return
            now = self.clock()
            current = next((item for trip_id, item in self.store.due(conn, start=now, end=now + DEFAULT_LOOKAHEAD)
                            if trip_id == issue.trip_id and item.item_id == issue.item.item_id), None)
            if current is None or any(getattr(current, field) != getattr(issue.item, field)
                                      for field in ("place_id", "starts_at", "ends_at", "kind", "title")):
                return
            for (previous,) in rows:
                for cause in issue.causes:
                    # 사건별 키를 써서 둘 중 하나가 해제돼도 남은 통제를 다시 보내지 않는다.
                    repair = traffic_detail_notice(item=current, causes=[cause], previous=previous)
                    if repair is None:
                        continue
                    fingerprint, payload = repair
                    added = self.store.enqueue_message(conn, trip_id=issue.trip_id,
                        key=f"watch-traffic-detail:{current.item_id}:{fingerprint}", payload=payload)
                    if added:
                        result.notified.append({"trip_id": str(issue.trip_id), "item": current.title,
                                                "reason": "notice_text_incomplete"})

    def _recover_existing(self, conn: Any, issue: Issue, case_id: str, group: list[Issue],
                          result: CaseTickResult, opened: list[UUID]) -> None:
        """직전 실행이 실패한 watch Case를 같은 판의 실행 관문으로 다시 보낸다."""
        from app.core.service_bindings import current_bindings

        identifier = UUID(str(case_id))
        if identifier in opened or self.run_case is None:
            return
        case = self.repository.get_case(conn, tenant_id=self.store.tenant_id, case_id=identifier)
        if case is None or str(case["status"]) != "running":
            return
        state = case.get("state_json") or {}
        table = current_bindings()
        # 운영 회차는 항상 고정 판이 있다. 명시 standalone 재생은 Controller 관문을 쓴다.
        if table is not None:
            try:
                registry = table.registry
                if registry is None:
                    raise TeamUnavailable(case["owner_team_id"], "composition_unbound")
                entry = registry.require_runnable(case["owner_team_id"])
                capability = registry.capability_for(entry, case.get("intent"),
                    input_text=state.get("customer_input") or case.get("subject"),
                    state={**state, "issue_code": case.get("issue_code")})
                registry.require_runnable(case["owner_team_id"], capability)
            except TeamUnavailable as exc:
                logger.warning("watch_recovery_unavailable team_id=%s reason=%s composition_revision=%s",
                               exc.team_id, exc.reason, table.revision)
                result.unavailable.append({"case_id": str(identifier), "kind": exc.team_id, "reason": exc.reason})
                return
        opened.append(identifier)
        result.retried.append({**issue.record(), "case_id": str(identifier), "same_case": True})
        trigger = state.get("trigger") or {}
        if "batch" in trigger:
            members = {str(member["item_id"]) for member in trigger["batch"]}
            self._contexts[identifier] = {"trip_id": issue.trip_id,
                                          "batch": [member for member in group if str(member.item.item_id) in members]}
        else:
            self._contexts[identifier] = {"trip_id": issue.trip_id, "item": issue.item, "causes": issue.causes}

    def _attempt(self, conn: Any, base_id: str, item_id: UUID) -> tuple[int | None, str | None]:
        """(몇 번째 시도인가, 덮은 Case). 이 문제(`base_id`)를 **덮은 Case** 가 단일이든 묶음이든 없으면 (0, None) — 새로 연다.
        있는데 **다시 열 만하면**(일시 실패로 닫혔다 · 묶음이 이 항목을 「다시 열 항목」으로 남겼다) 한도 안이고 식힘 시간이 지났을 때 (몇 번째 재시도, …) — 다시 연다.
        실행 실패로 멈춘 running이면 (0, 기존 Case) — 새로 열지 않고 같은 Case를 실행한다.
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
                "         ORDER BY e.aggregate_version DESC LIMIT 1), '[]'::jsonb), "
                "       (NOT EXISTS (SELECT 1 FROM agent_runs r WHERE r.tenant_id=c.tenant_id "
                "          AND r.case_id=c.case_id AND r.status IN ('active','running','resuming')) "
                "        AND (SELECT r.status FROM agent_runs r WHERE r.tenant_id=c.tenant_id AND r.case_id=c.case_id "
                "             ORDER BY r.started_at DESC, r.run_id DESC LIMIT 1) = 'failed') "
                "FROM customer_cases c WHERE c.tenant_id=%s "
                "AND (c.state_json->>'request_id' = %s OR c.state_json->>'request_id' LIKE %s "
                "     OR c.state_json->'trigger'->'batch' @> %s::jsonb) "
                "ORDER BY c.created_at DESC LIMIT 1",
                (self.store.tenant_id, base_id, f"{base_id}:r%", json.dumps([{"base_id": base_id}])))
            row = cur.fetchone()
        if row is None:
            return 0, None
        case_id, status, quiet, guardrail, total = row[0], row[1], float(row[2]), row[3], int(row[4])
        if str(status) == "running" and row[8]:
            return 0, str(case_id)
        is_batch, retry_ids = bool(row[5]), [str(x) for x in (row[6] or [])]
        observed = (" ".join(str(x) for x in row[7]) if isinstance(row[7], list) else str(row[7] or ""))
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
        """한 여행의 문제 둘 이상 — 묶음 Case 하나. 라벨은 진입 표지이고 처리 계획은 분류 에이전트가 정한다.
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
                                    "attempt": attempt,
                                    "issue_code": i.issue_code,
                                    "categories": sorted({str(c.get("category")) for c in i.causes})} for i, attempt in chunk],
                         "at": now.isoformat(), "detected": "batch",
                         "categories": sorted({str(c.get("category")) for i in issues for c in i.causes})},
                labels={"intent": "incident_report", "issue_code": issues[0].issue_code, "sentiment": "neutral"})
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
        재시도 가능한 실패에는 표지가 없어도 기존 일정 유지·재확인 안내를 남긴다."""
        from app.domains.travel_ops.components.watch.trip_watch_batch import Outcome, digest, guidance_key

        guardrail, observed = self._escalation(case_id)
        issues = {str(i.item.item_id): i for i in context["batch"]}
        if guardrail == "action_rejected" and observed.startswith(RECHECK_FAILED):
            # ★`[2026-10-03 적대 검토]` Team 이 낸 묶음을 적용기가 일정 전체 재판정으로 **거절**했다 — 단일 Case 처럼 고객에게 알린다(구성원 전원이 「그대로 두었어요」). 안 알리면 구성원 전부가 말없이 막힌다
            found = [(item_id, "recheck_failed") for item_id in issues]
        else:
            found = [(match.group(1), match.group(2))
                     for match in re.finditer(r"outcome:([0-9a-fA-F-]{36}):(no_alternate|recheck_failed|source_failed|error|retry)", observed)]
            if not found and guardrail in RETRYABLE_GUARDRAILS:
                found = [(item_id, "retry") for item_id in issues]
            elif not found:
                # ★`[2026-10-14]` 항목 표지 없이 다시 시도하지 않는 실패로 끝났다 — 전에는 구성원 전원이 말없이 남았다(단일 Case 의 `_unhandled_notice` 와 같다)
                found = [(item_id, "unhandled") for item_id in issues]
        outcomes = [Outcome(issues[item_id].item, kind, causes=issues[item_id].causes,
                            reasons=[_code(guardrail) if kind == "unhandled" else (guardrail or kind)],
                            checked_at=self.clock().isoformat())
                    for item_id, kind in found if item_id in issues]
        # ★`[2026-10-03 사용자 지적]` 못 푼 항목마다 조건을 푼 안을 먼저 묻는다 — 묻는 항목은 이 「그대로 두었어요」 알림에서 빠진다(제안 알림이 따로 나간다). 하나도 없는 항목만 남는다
        outcomes = [o for o in outcomes
                    if o.kind in ("source_failed", "error", "retry", "unhandled") or
                    not self._offer_relaxed(context["trip_id"], o.item, o.causes, o.kind == "recheck_failed", result, case_id)]
        if not outcomes:
            return
        payload = digest(outcomes, kind="guidance")
        with self._connect() as conn, conn.transaction():
            self.store.enqueue_message(conn, trip_id=context["trip_id"], key=f"watch-unresolved:batch:{guidance_key(payload)}", payload=payload)
        result.notified.append({"case_id": str(case_id), "trip_id": str(context["trip_id"]),
                                "item": ", ".join(o.item.title for o in outcomes)})


    def _recover_existing(self, conn: Any, issue: Issue, case_id: str, group: list[Issue],
                          result: CaseTickResult, opened: list[UUID]) -> None:
        """직전 실행이 실패한 watch Case를 같은 판의 실행 관문으로 다시 보낸다."""
        from app.core.service_bindings import current_bindings

        identifier = UUID(str(case_id))
        if identifier in opened or self.run_case is None:
            return
        case = self.repository.get_case(conn, tenant_id=self.store.tenant_id, case_id=identifier)
        if case is None or str(case["status"]) != "running":
            return
        state = case.get("state_json") or {}
        table = current_bindings()
        # 운영 회차는 항상 고정 판이 있다. 명시 standalone 재생은 Controller 관문을 쓴다.
        if table is not None:
            try:
                registry = table.registry
                if registry is None:
                    raise TeamUnavailable(case["owner_team_id"], "composition_unbound")
                entry = registry.require_runnable(case["owner_team_id"])
                capability = registry.capability_for(entry, case.get("intent"),
                    input_text=state.get("customer_input") or case.get("subject"),
                    state={**state, "issue_code": case.get("issue_code")})
                registry.require_runnable(case["owner_team_id"], capability)
            except TeamUnavailable as exc:
                logger.warning("watch_recovery_unavailable team_id=%s reason=%s composition_revision=%s",
                               exc.team_id, exc.reason, table.revision)
                result.unavailable.append({"case_id": str(identifier), "kind": exc.team_id, "reason": exc.reason})
                return
        opened.append(identifier)
        result.retried.append({**issue.record(), "case_id": str(identifier), "same_case": True})
        trigger = state.get("trigger") or {}
        if "batch" in trigger:
            members = {str(member["item_id"]) for member in trigger["batch"]}
            self._contexts[identifier] = {"trip_id": issue.trip_id,
                                          "batch": [member for member in group if str(member.item.item_id) in members]}
        else:
            self._contexts[identifier] = {"trip_id": issue.trip_id, "item": issue.item, "causes": issue.causes}


__all__ = ["CaseTickResult", "DEFAULT_LOOKAHEAD", "RETRYABLE_GUARDRAILS", "TripWatchCaseOpener"]
