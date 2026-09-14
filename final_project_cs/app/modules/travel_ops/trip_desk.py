# -*- coding: utf-8 -*-
"""고객이 먼저 알린 사건 — 늦음 · 도착해 보니 휴무 · 「근처 다른 곳 없어?」.

★확정 시나리오의 여섯 사건 중 셋(요식-P3 · 요식-P7 · 액-08)은 **고객이 겪거나 물어서**
  시작한다(설계대응 §0). 감시 루프가 못 보는 것이다 — 식당 당일 휴무·매장 재고는
  소스가 없다.

★이 파일은 **도메인 판단**만 한다. 고객 문장을 받는 입구(에이전트 API → Case →
  분류 `incident_report`·`confirm_request` → Team)는 이 함수들을 부르는 쪽이다.
  `[미구현]` 그 배선은 다음 단계다 — 지금은 재생 시험이 여기를 직접 부른다.

★고객 신고는 **근거가 고객 문장**이다. 「고객이 휴무라고 알렸다」를 근거로 남기고,
  우리 확인처럼 말하지 않는다(v11 §4-D).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from .itinerary import Item, StaleItinerary, TripStore
from .replan import (SEATING_BUFFER_MIN, WALK_M_PER_MIN, choose, dining_candidates,
                     dining_fits, dining_notice, store_candidates)

#: 대안 식당을 찾는 반경(미터). ★우리가 고른 값이다 — 도보 약 9분.
DINING_RADIUS_M = 700


def _minutes(start: datetime, end: datetime | None, default: int = 60) -> int:
    return default if end is None else int((end - start).total_seconds() // 60)


def _object_particle(word: str) -> str:
    """을/를. 마지막 글자가 한글이 아니면 「을(를)」로 둔다 — 틀리게 붙이지 않는다."""
    last = word.strip()[-1:] if word.strip() else ""
    if not ("가" <= last <= "힣"):
        return "을(를)"
    return "을" if (ord(last) - 0xAC00) % 28 else "를"


def _round_up_5(moment: datetime) -> datetime:
    extra = (-moment.minute) % 5
    return (moment + timedelta(minutes=extra)).replace(second=0, microsecond=0)


class TripDesk:
    def __init__(self, *, store: TripStore, connection_factory: Callable[[], Any]) -> None:
        self.store, self._connect = store, connection_factory

    # ── 요식-P3 — 늦는다 ────────────────────────────────────────
    def report_delay(self, *, trip_id: UUID, at: datetime, minutes: int,
                     message: str) -> dict[str, Any]:
        """「N분 늦는다」. 다음 식사 항목이 그 도착 시각에 성립하는지 보고, 안 되면 바꾼다."""
        with self._connect() as conn:
            trip, items = self.store.latest(conn, trip_id)
            places = self.store.places(conn)
        meal = next((i for i in items if i.kind == "dining" and i.starts_at >= at), None)
        if meal is None or meal.place is None:
            return {"status": "no_meal", "message": "늦어지는 시각 뒤에 식사 일정이 없다"}
        arrival = meal.starts_at + timedelta(minutes=minutes)
        duration = _minutes(meal.starts_at, meal.ends_at)
        fits, why = dining_fits(meal.place, arrival, duration)
        cause = {"category": "customer_report", "type": "delay", "minutes": minutes,
                 "message": message, "evidence": "고객 신고"}
        if fits is True:
            return {"status": "still_fits", "arrival": arrival.isoformat()}
        following = next((i for i in items if i.seq > meal.seq), None)
        candidates = dining_candidates(
            original=meal.place, places=places, arrival=arrival, minutes=duration,
            constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
            next_start=following.starts_at if following else None)
        best, alternates, rejected = choose(candidates)
        if best is None:
            return {"status": "unresolved", "reason": why,
                    "rejected": {c.name: c.rejected for c in rejected}}
        notice = dining_notice(
            original=meal.place, best=best, alternates=alternates,
            reason=f"점심 도착이 {arrival:%H:%M}(으)로 늦어져 {meal.place['name']}은 {why}",
            cause=cause, after=None, constraint_note="브레이크타임 없는")
        return self._apply(trip_id, meal, best, notice)

    # ── 요식-P7 — 도착했더니 휴무 ──────────────────────────────
    def report_closed(self, *, trip_id: UUID, at: datetime, message: str) -> dict[str, Any]:
        """「오늘 임시휴무」. 지금 식사 항목을 걸어갈 수 있는 대체 식당으로 바꾼다."""
        with self._connect() as conn:
            trip, items = self.store.latest(conn, trip_id)
            places = self.store.places(conn)
        meal = next((i for i in items if i.kind == "dining"
                     and i.starts_at <= at < (i.ends_at or i.starts_at + timedelta(hours=1))), None)
        if meal is None or meal.place is None:
            return {"status": "no_meal", "message": "지금 시각에 식사 일정이 없다"}
        duration = _minutes(meal.starts_at, meal.ends_at)
        following = next((i for i in items if i.seq > meal.seq), None)
        cause = {"category": "customer_report", "type": "closed_today", "message": message,
                 "evidence": "고객 신고 — 현장 안내문"}
        # 후보마다 도보 시간이 달라 입장 시각도 다르다 — 먼저 거리로 입장 시각을 잡는다.
        candidates = []
        for place in places:
            if place.get("kind") != "dining" or place["place_id"] == meal.place["place_id"]:
                continue
            probe = dining_candidates(
                original=meal.place, places=[place], arrival=at, minutes=duration,
                constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
                next_start=None)
            if not probe:
                continue
            walk = probe[0].walk_min or 0
            arrival = _round_up_5(at + timedelta(minutes=walk + SEATING_BUFFER_MIN))
            candidates += dining_candidates(
                original=meal.place, places=[place], arrival=arrival, minutes=duration,
                constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
                next_start=following.starts_at if following else None)
        best, alternates, rejected = choose(candidates)
        if best is None:
            return {"status": "unresolved", "rejected": {c.name: c.rejected for c in rejected}}
        after = None
        later_activity = next((i for i in items if i.seq > meal.seq and i.kind == "activity"), None)
        if later_activity and best.ends_at and best.ends_at <= later_activity.starts_at:
            after = later_activity.place["name"] if later_activity.place else later_activity.title
        payment = (trip.get("constraints") or {}).get("payment")
        notice = dining_notice(
            original=meal.place, best=best, alternates=alternates,
            reason=f"{meal.place['name']}이(가) 오늘 임시휴무라고 알려 주셨습니다",
            cause=cause, after=after,
            constraint_note="카드 결제가 가능한" if payment == "card" else None)
        return self._apply(trip_id, meal, best, notice)

    # ── 액-08 — 품절, 근처 다른 곳? ────────────────────────────
    def ask_nearby_store(self, *, trip_id: UUID, at: datetime, products: list[str],
                         message: str) -> dict[str, Any]:
        """품절 상품을 **취급할 만한** 매장을 귀가 동선에서 고른다. 일정은 안 바꾼다.

        ★재고는 확인하지 않는다 — 재고 소스가 없다(§7-C 3단계). 그래서 답에
          `[미확인]` 을 붙인다. 「있다」고 말하지 않는다.
        """
        with self._connect() as conn:
            trip, items = self.store.latest(conn, trip_id)
            places = self.store.places(conn)
        here_item = next((i for i in items if i.kind == "activity"
                          and i.starts_at <= at < (i.ends_at or at)), None)
        home = next((i.place for i in items if i.place and i.place.get("kind") == "lodging"), None)
        if here_item is None or here_item.place is None or home is None:
            return {"status": "unresolved", "message": "지금 위치나 숙소를 알 수 없다"}
        candidates = store_candidates(here=here_item.place, home=home, places=places,
                                      products=products, at=at)
        best, alternates, rejected = choose(candidates)
        if best is None:
            return {"status": "unresolved", "rejected": {c.name: c.rejected for c in rejected}}
        detour = (best.option or {}).get("detour_m") or 0
        # ★100m 안쪽이면 「돌아가는 거리」를 숫자로 말하지 않는다 — 9m·1분 같은 값은
        #   정밀해 보이지만 좌표 근사에서 나온 잡음이다.
        extra = ("거의 돌아가지 않아도 됩니다" if detour < 100 else
                 f"돌아가는 거리 약 {detour}m 추가, 도보 약 {max(1, round(detour / WALK_M_PER_MIN))}분")
        listed = ", ".join(products)
        text = (f"{best.name}이(가) 호텔로 돌아가는 동선 위에 있습니다({extra}). "
                f"{listed}{_object_particle(listed)} 취급하는 매장이지만 지금 재고는 확인하지 "
                f"못했습니다[미확인].")
        return {"status": "answered", "text": text, "recommendation": best.name,
                "stock": "unverified", "other_options": [c.name for c in alternates],
                "rejected": {c.name: c.rejected for c in rejected},
                "cause": {"category": "customer_report", "type": "stock_out",
                          "products": products, "message": message}}

    # ── 적용(버전 + 통지를 한 트랜잭션) ─────────────────────────
    def _apply(self, trip_id: UUID, meal: Item, best, notice: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn, conn.transaction():
            trip, items = self.store.latest(conn, trip_id)
            new_items = [current.replaced_by(
                place=best.place, title=f"{best.name} 식사", starts_at=best.starts_at,
                ends_at=best.ends_at,
                detail={"other_options": notice["other_options"], "customer_reported": True})
                if current.item_id == meal.item_id else current for current in items]
            try:
                version = self.store.append_version(
                    conn, trip_id=trip_id, base_version=trip["version"], items=new_items,
                    reason="customer_report", causes=notice["causes"])
            except StaleItinerary:
                return {"status": "stale"}
            self.store.enqueue_notice(conn, trip_id=trip_id, version=version,
                                      payload={**notice, "version": version})
        return {"status": "adjusted", "version": version, "to": best.name, "notice": notice}


__all__ = ["DINING_RADIUS_M", "TripDesk"]
