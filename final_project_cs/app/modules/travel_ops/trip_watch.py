# -*- coding: utf-8 -*-
"""일정 감시 — **곧 시작할 항목**을 점검하고, 깨졌으면 먼저 고쳐 알린다(시나리오용 여행 버전).

★`watch.py` 는 **장소 정보**(이름·주소·좌표·분류)가 바뀐 것을 본다. 시나리오의 사건은
  **운영 상태**(미세먼지 경보·운행 중단·통제·휴무)라 거기서 안 잡힌다(설계대응 §3).
  이 파일은 일정 항목마다 점검한다 — 장소 항목은 성립 점검(`DisruptionCheck`),
  이동 항목은 **경로 점검**(구간에 걸린 무정차·통제 사건).

★한 틱이 하는 일(v11 §6-C 의 MVP 판):
    1  앞으로 `lookahead` 안에 시작하는 항목을 최신 일정 버전에서 고른다
    2  항목마다 점검
    3  `disrupted` → 대안 후보 → 탈락·재검증·사전식 비교로 **하나** → 새 일정 버전 +
       통지(같은 트랜잭션)
       `fatal`   → 고치지 않는다. 재검토 필요로 남긴다(결정 15 의 치명 — 부분 반영 금지)
    4  같은 사건으로 두 번 고치지 않는다 — 대체 항목은 원인이 사라진 곳이라 다음 틱의
       점검이 `clear` 가 된다. 그래도 겹치면 기준 버전 조건이 막는다

★`[2026-09-17]` **대안 계산은 `itinerary_changes.py` 가 한다** — Case 버전의 감시 Case
  (`trip_watch_cases.py`)와 Team 이 같은 계산을 쓴다. 이 파일은 점검·읽기·쓰기만 한다.
  옮기기 전 원본: `legacy/final_project_cs/app/modules/travel_ops/trip_watch.py`.

★`[미구현]` 식사 항목의 **시스템 감지**(당일 휴무 등)는 소스가 없다 — 요식-P3·P7 은
  고객 신고로 들어온다(`trip_desk.py`). 식사 항목이 여기서 깨지면 `unhandled` 로 센다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from .itinerary import Item, StaleItinerary, TripStore
from .itinerary_changes import (ItineraryChange, NoChange, next_after, plan_activity_adjustment,
                                plan_route_adjustment, planned_option, route_of, route_targets)

DEFAULT_LOOKAHEAD = timedelta(minutes=90)


@dataclass
class TripTickResult:
    checked: int = 0
    adjusted: list[dict[str, Any]] = field(default_factory=list)
    fatal: list[dict[str, Any]] = field(default_factory=list)
    unhandled: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    pinned: list[dict[str, Any]] = field(default_factory=list)
    #: 경로 사건 소스가 **답할 수 없는** 대상(지하철 무정차 등) — 「사건 없음」과 다르다.
    unchecked: list[dict[str, Any]] = field(default_factory=list)


class TripWatcher:
    def __init__(self, *, store: TripStore, check: Callable[..., dict[str, Any]],
                 connection_factory: Callable[[], Any], clock: Callable[[], datetime],
                 routes: dict[str, Any] | None = None, route_events: Any = None) -> None:
        self.store, self.check = store, check
        self._connect, self.clock = connection_factory, clock
        self.routes, self.route_events = routes or {}, route_events

    def tick(self, lookahead: timedelta = DEFAULT_LOOKAHEAD) -> TripTickResult:
        result = TripTickResult()
        now = self.clock()
        with self._connect() as conn:
            due = self.store.due(conn, start=now, end=now + lookahead)
            places = self.store.places(conn)
        for trip_id, item in due:
            if item.detail.get("customer_pinned"):
                # ★고객이 되돌려 고른 항목은 다시 자동으로 바꾸지 않는다. 안 그러면
                #   되돌림 → 다음 틱 자동 변경 → 되돌림 … 이 끝없이 돈다. 세어서 남긴다.
                result.pinned.append({"trip_id": str(trip_id), "item": item.title})
                continue
            if item.kind == "mobility":
                result.checked += 1
                self._check_route(trip_id, item, now, result)
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
            plan = plan_activity_adjustment(item=item, report=report, places=places,
                                            check=self.check, now=now)
            self._settle(trip_id, item, plan, result)
        return result

    # ── 이동 ───────────────────────────────────────────────────
    def _check_route(self, trip_id, item, now, result) -> None:
        route = route_of(item, self.routes)
        if not route or self.route_events is None:
            return
        _, planned = planned_option(item, route)
        events = self.route_events.affecting(route_targets(route))
        if events is None:
            # ★경로 사건을 못 읽었다 — 「사건 없음」으로 넘기지 않는다(결정 15 의 치명).
            result.fatal.append({"trip_id": str(trip_id), "item": item.title,
                                 "report": {"verdict": "fatal",
                                            "failed_categories": ["route_events"]}})
            return
        unsupported = getattr(self.route_events, "unsupported", None)
        blind = unsupported(planned.get("uses", [])) if callable(unsupported) else []
        if blind:
            result.unchecked.append({"trip_id": str(trip_id), "item": item.title,
                                     "targets": blind})
        if not any(target in events for target in planned.get("uses", [])):
            return
        with self._connect() as conn:
            _, items = self.store.latest(conn, trip_id)
        plan = plan_route_adjustment(item=item, following=next_after(items, item), route=route,
                                     events=events, now=now)
        self._settle(trip_id, item, plan, result)

    def _settle(self, trip_id, item: Item, plan, result: TripTickResult) -> None:
        if isinstance(plan, NoChange):
            if plan.status == "unresolved":
                result.unresolved.append({"trip_id": str(trip_id), "item": item.title,
                                          **plan.detail})
            return
        self._apply(trip_id, item, plan, result)

    # ── 적용(버전 + 통지를 한 트랜잭션) ─────────────────────────
    def _apply(self, trip_id, item: Item, plan: ItineraryChange, result: TripTickResult) -> None:
        with self._connect() as conn, conn.transaction():
            trip, items = self.store.latest(conn, trip_id)
            if not any(current.item_id == item.item_id for current in items):
                return   # ★그 사이 다른 쪽이 이 항목을 이미 바꿨다 — 옛 계산을 밀어 넣지 않는다
            try:
                version = self.store.append_version(
                    conn, trip_id=trip_id, base_version=trip["version"],
                    items=plan.new_items(items), reason=plan.reason, causes=plan.causes)
            except StaleItinerary:
                return
            self.store.enqueue_notice(conn, trip_id=trip_id, version=version,
                                      payload={**plan.notice, "version": version})
        result.adjusted.append({"trip_id": str(trip_id), "version": version, **plan.summary,
                                "notice": plan.notice})


__all__ = ["DEFAULT_LOOKAHEAD", "TripTickResult", "TripWatcher"]
