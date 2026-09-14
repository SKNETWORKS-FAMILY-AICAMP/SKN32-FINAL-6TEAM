# -*- coding: utf-8 -*-
"""일정 감시 — **곧 시작할 항목**을 점검하고, 깨졌으면 먼저 고쳐 알린다.

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

★`[미구현]` 식사 항목의 **시스템 감지**(당일 휴무 등)는 소스가 없다 — 요식-P3·P7 은
  고객 신고로 들어온다(`trip_desk.py`). 식사 항목이 여기서 깨지면 `unhandled` 로 센다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from .itinerary import Item, StaleItinerary, TripStore
from .replan import (activity_candidates, alternate_record, change_notice, choose,
                     route_candidates, route_notice)

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


def _next_after(items: list[Item], item: Item) -> Item | None:
    later = [other for other in items if other.seq > item.seq]
    return min(later, key=lambda other: other.seq) if later else None


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
            self._adjust_activity(trip_id, item, report, places, now, result)
        return result

    # ── 활동 ───────────────────────────────────────────────────
    def _adjust_activity(self, trip_id, item, report, places, now, result) -> None:
        causes = report.get("disruptions", [])
        candidates = activity_candidates(original=item.place, places=places,
                                         start=item.starts_at, end=item.ends_at, causes=causes)
        best, alternates, rejected = choose(
            candidates, lambda c: self.check(place=c.place, starts_at=item.starts_at))
        if best is None:
            # ★못 풀면 부분 반영하지 않는다(§6-C-5). 사람에게 넘길 재료를 남긴다.
            result.unresolved.append({"trip_id": str(trip_id), "item": item.title,
                                      "causes": causes,
                                      "rejected": {c.name: c.rejected for c in rejected}})
            return
        replay = any(cause.get("mode") == "replay" for cause in causes)
        notice = change_notice(original=item.place, replacement=best.place,
                               start=item.starts_at, causes=causes,
                               alternates=alternates, replay=replay)
        replacement = lambda current: current.replaced_by(  # noqa: E731
            place=best.place, title=f"{best.place['name']} 관람",
            detail={"auto_adjusted_at": now.isoformat(),
                    "other_options": notice["other_options"],
                    "alternates": [alternate_record(c) for c in alternates]})
        self._apply(trip_id, item, replacement, causes, notice, result,
                    summary={"from": item.place["name"], "to": best.place["name"]})

    # ── 이동 ───────────────────────────────────────────────────
    def _check_route(self, trip_id, item, now, result) -> None:
        # ★경로 정의는 항목이 들고 온다(`route_def`, 등록 API 가 넣는다). 재생 시험처럼
        #   밖에서 준 `routes` 가 있으면 그것이 먼저다.
        route = self.routes.get(str(item.detail.get("route"))) or item.detail.get("route_def")
        if not route or self.route_events is None:
            return
        options = {option["id"]: option for option in route["options"]}
        chosen = str(item.detail.get("option") or route["planned"])
        planned = options.get(chosen, {})
        targets = sorted({target for option in options.values()
                          for target in option.get("uses", [])})
        events = self.route_events.affecting(targets)
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
        hit = {target: events[target] for target in planned.get("uses", []) if target in events}
        if not hit:
            return
        causes = [{"category": "route_event", "target": target, **event}
                  for target, event in hit.items()]
        with self._connect() as conn:
            _, items = self.store.latest(conn, trip_id)
        following = _next_after(items, item)
        candidates = route_candidates(
            route={**route, "planned": chosen}, depart=item.starts_at,
            planned_arrival=item.ends_at or item.starts_at,
            next_start=following.starts_at if following else None, events=events)
        best, alternates, rejected = choose(candidates)
        if best is None:
            result.unresolved.append({"trip_id": str(trip_id), "item": item.title,
                                      "causes": causes,
                                      "rejected": {c.name: c.rejected for c in rejected}})
            return
        replay = any(cause.get("mode") == "replay" for cause in causes)
        next_title = following.title if following else None
        notice = route_notice(route={**route, "planned": chosen}, planned=planned, best=best,
                              alternates=alternates, rejected=rejected, causes=causes,
                              planned_arrival=item.ends_at or item.starts_at,
                              next_title=next_title, replay=replay)
        replacement = lambda current: current.replaced_by(  # noqa: E731
            place=None, title=f"{route['from']} → {route['to']} · {(best.option or {}).get('label')}",
            starts_at=best.starts_at, ends_at=best.ends_at,
            detail={**current.detail, "option": best.key,
                    "auto_adjusted_at": now.isoformat(),
                    "other_options": notice["other_options"],
                    "alternates": [alternate_record(c) for c in alternates]})
        self._apply(trip_id, item, replacement, causes, notice, result,
                    summary={"from": planned.get("label"),
                             "to": (best.option or {}).get("label")})

    # ── 적용(버전 + 통지를 한 트랜잭션) ─────────────────────────
    def _apply(self, trip_id, item, replacement, causes, notice, result, *, summary) -> None:
        with self._connect() as conn, conn.transaction():
            trip, items = self.store.latest(conn, trip_id)
            if not any(current.item_id == item.item_id for current in items):
                return   # ★그 사이 다른 쪽이 이 항목을 이미 바꿨다 — 옛 계산을 밀어 넣지 않는다
            new_items = [replacement(current) if current.item_id == item.item_id else current
                         for current in items]
            try:
                version = self.store.append_version(
                    conn, trip_id=trip_id, base_version=trip["version"], items=new_items,
                    reason="auto_adjusted", causes=causes)
            except StaleItinerary:
                return
            self.store.enqueue_notice(conn, trip_id=trip_id, version=version,
                                      payload={**notice, "version": version})
        result.adjusted.append({"trip_id": str(trip_id), "version": version, **summary,
                                "notice": notice})


__all__ = ["DEFAULT_LOOKAHEAD", "TripTickResult", "TripWatcher"]
