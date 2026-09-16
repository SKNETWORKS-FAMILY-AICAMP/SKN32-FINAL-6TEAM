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

★`fatal`(결정 15 — 대체 소스까지 실패)·`unhandled`(식사 항목의 시스템 감지 소스 없음)·
  `unchecked`(경로 소스가 답할 수 없는 대상)는 시나리오 버전과 같게 **센다.**
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from app.application.case_intake import open_case

from .itinerary import Item, TripStore
from .itinerary_changes import planned_option, route_of, route_targets
from .replan import WEATHER_LIKE
from .subjects import KIND, resolve_subject

DEFAULT_LOOKAHEAD = timedelta(minutes=90)
ACTOR = "trip_watch"


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
        with self._connect() as conn:
            due = self.store.due(conn, start=now, end=now + lookahead)
        opened: list[UUID] = []
        for trip_id, item in due:
            if item.detail.get("customer_pinned"):
                result.pinned.append({"trip_id": str(trip_id), "item": item.title})
                continue
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
            if item.kind != "activity":
                result.unhandled.append(entry)
                continue
            causes = report.get("disruptions", [])
            weather = any(cause.get("category") in WEATHER_LIKE for cause in causes)
            self._open(trip_id, item, now, result, opened, causes=causes,
                       issue_code="activity_weather_risk" if weather else "activity_other",
                       detected="place")
        # ★Case 를 다 연 **뒤에** 돌린다 — 커넥션을 잡은 채 Team 을 기다리지 않는다.
        if self.run_case is not None:
            for case_id in opened:
                outcome = self.run_case(tenant_id=self.store.tenant_id, case_id=case_id, actor_id=ACTOR)
                result.ran.append({"case_id": str(case_id), "status": (outcome or {}).get("status")})
        return result

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
        request_id = f"watch:{trip_id}:{item.item_id}:{_fingerprint(causes)}"
        with self._connect() as conn:
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
        else:
            result.existing.append(record)


__all__ = ["CaseTickResult", "DEFAULT_LOOKAHEAD", "TripWatchCaseOpener"]
