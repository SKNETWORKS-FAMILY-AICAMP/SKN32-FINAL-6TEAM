# -*- coding: utf-8 -*-
"""고객이 먼저 알린 사건과 재요청 — 늦음 · 도착해 보니 휴무 · 「근처 다른 곳 없어?」 ·
「다른 안으로 바꿔 줘」 · 「되돌려 줘」 — **시나리오용 여행 버전**의 창구.

★확정 시나리오의 여섯 사건 중 셋(요식-P3 · 요식-P7 · 액-08)은 **고객이 겪거나 물어서**
  시작한다(설계대응 §0). 감시 루프가 못 보는 것이다 — 식당 당일 휴무·매장 재고는
  소스가 없다.

★재요청 둘(v11 §1 접점 · DoD-8/9) — 최고 안 하나를 먼저 적용하고 알린 뒤, 마음에 안
  들면 고객이 **다른 안으로 바꾸거나** **옛 버전으로 되돌린다.** 알림을 승인 요청으로
  쓰지 않기 때문에 이 두 길이 있어야 성립한다.

★`[2026-09-17]` **계산은 `itinerary_changes.py` 가 한다.** 이 파일은 읽고 → 계산을 부르고 →
  쓴다. Case 버전의 Team 이 같은 계산을 쓰므로 두 버전의 문구·판단이 갈리지 않는다.
  옮기기 전 원본: `legacy/final_project_cs/app/modules/travel_ops/trip_desk.py`.
  `[정정 2026-09-17]` 이 머리말은 「자유 문장 배선 `[미구현]`」·「입구는
  `app/presentation/api/trips.py`」라고 적혀 있었다 — 배선은 `trip_messages.py` 에 있고
  입구 파일은 `trip_api.py` 다.

★고객 신고는 **근거가 고객 문장**이다. 「고객이 휴무라고 알렸다」를 근거로 남기고,
  우리 확인처럼 말하지 않는다(v11 §4-D).

★요청 id 를 원인 칸에 남긴다 — 같은 신고를 두 번 받아 두 번 고치지 않게
  (`TripStore.version_for_request`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from .itinerary import Item, StaleItinerary, TripStore
from .itinerary_changes import (DINING_RADIUS_M, ItineraryChange, NoChange, Plan, plan_closed,
                                plan_delay, plan_nearby_store, plan_rollback, plan_swap)


class TripDesk:
    def __init__(self, *, store: TripStore, connection_factory: Callable[[], Any],
                 check: Callable[..., dict[str, Any]] | None = None) -> None:
        self.store, self._connect = store, connection_factory
        # ★다른 안으로 바꿀 때 활동이면 **그 시각에 다시 점검**한다 — 계산한 뒤로 시간이
        #   흘렀다. 점검기가 없으면(재생 시험 일부) 점검 없이 바꾼다고 결과에 적는다.
        self._check = check

    def _read(self, trip_id: UUID):
        with self._connect() as conn:
            trip, items = self.store.latest(conn, trip_id)
            places = self.store.places(conn)
        return trip, items, places

    # ── 요식-P3 — 늦는다 ────────────────────────────────────────
    def report_delay(self, *, trip_id: UUID, at: datetime, minutes: int,
                     message: str, request_id: str | None = None) -> dict[str, Any]:
        """「N분 늦는다」. 다음 식사 항목이 그 도착 시각에 성립하는지 보고, 안 되면 바꾼다."""
        trip, items, places = self._read(trip_id)
        plan = plan_delay(trip=trip, items=items, places=places, at=at, minutes=minutes,
                          message=message, request_id=request_id)
        return self._outcome(trip_id, trip["version"], items, plan)

    # ── 요식-P7 — 도착했더니 휴무 ──────────────────────────────
    def report_closed(self, *, trip_id: UUID, at: datetime, message: str,
                      request_id: str | None = None) -> dict[str, Any]:
        """「오늘 임시휴무」. 지금 식사 항목을 걸어갈 수 있는 대체 식당으로 바꾼다."""
        trip, items, places = self._read(trip_id)
        plan = plan_closed(trip=trip, items=items, places=places, at=at, message=message,
                           request_id=request_id)
        return self._outcome(trip_id, trip["version"], items, plan)

    # ── 액-08 — 품절, 근처 다른 곳? ────────────────────────────
    def ask_nearby_store(self, *, trip_id: UUID, at: datetime, products: list[str],
                         message: str, request_id: str | None = None) -> dict[str, Any]:
        """품절 상품을 **취급할 만한** 매장을 귀가 동선에서 고른다. 일정은 안 바꾼다."""
        _, items, places = self._read(trip_id)
        return plan_nearby_store(items=items, places=places, at=at, products=products,
                                 message=message, request_id=request_id)

    # ── 재요청 ① — 다른 안으로 바꿔 줘 ─────────────────────────
    def swap_alternate(self, *, trip_id: UUID, item_id: UUID, base_version: int,
                       choice: str | None = None, message: str | None = None,
                       request_id: str | None = None) -> dict[str, Any]:
        """적용된 안을 들고 있던 「다른 안」으로 바꾼다. 원래 안은 다시 「다른 안」이 된다."""
        trip, items, places = self._read(trip_id)
        plan = plan_swap(trip_version=trip["version"], base_version=base_version, items=items,
                         places_by_id={p["place_id"]: p for p in places}, item_id=item_id,
                         choice=choice, message=message, request_id=request_id,
                         check=self._check)
        return self._outcome(trip_id, base_version, items, plan)

    # ── 재요청 ② — 되돌려 줘 ───────────────────────────────────
    def rollback(self, *, trip_id: UUID, base_version: int, to_version: int,
                 message: str | None = None, request_id: str | None = None) -> dict[str, Any]:
        """옛 버전의 항목을 **새 버전으로 다시 쓴다**(append-only — 옛 버전을 지우지 않는다)."""
        with self._connect() as conn:
            trip, items = self.store.latest(conn, trip_id)
            old = (self.store.items(conn, trip_id, to_version)
                   if trip["version"] == base_version and 1 <= to_version < trip["version"] else [])
        plan = plan_rollback(trip_version=trip["version"], base_version=base_version,
                             current_items=items, old_items=old, to_version=to_version,
                             message=message, request_id=request_id)
        if isinstance(plan, NoChange):
            return {"status": plan.status, **plan.detail}
        written = self._write(trip_id, base_version, items, plan)
        if written["status"] != "adjusted":
            return written
        return {"status": "rolled_back", "version": written["version"],
                "restored": plan.summary["restored"], "notice": plan.notice}

    # ── 적용(버전 + 통지를 한 트랜잭션) ─────────────────────────
    def _outcome(self, trip_id: UUID, base_version: int, items: list[Item],
                 plan: Plan) -> dict[str, Any]:
        if isinstance(plan, NoChange):
            return {"status": plan.status, **plan.detail}
        outcome = self._write(trip_id, base_version, items, plan)
        if outcome["status"] == "adjusted":
            outcome.update(plan.summary)
        return outcome

    def _write(self, trip_id: UUID, base_version: int, items: list[Item],
               plan: ItineraryChange) -> dict[str, Any]:
        """★계산에 쓴 버전(`base_version`) 위에만 쓴다. 그 사이 바뀌었으면 `stale`."""
        with self._connect() as conn, conn.transaction():
            try:
                version = self.store.append_version(
                    conn, trip_id=trip_id, base_version=base_version,
                    items=plan.new_items(items), reason=plan.reason, causes=plan.causes)
            except StaleItinerary:
                return {"status": "stale"}
            self.store.enqueue_notice(conn, trip_id=trip_id, version=version,
                                      payload={**plan.notice, "version": version})
        return {"status": "adjusted", "version": version, "notice": plan.notice}


__all__ = ["DINING_RADIUS_M", "TripDesk"]
