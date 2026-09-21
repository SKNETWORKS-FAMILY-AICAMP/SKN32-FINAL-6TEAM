# -*- coding: utf-8 -*-
"""고객이 먼저 알린 사건과 재요청 — 늦음 · 도착해 보니 휴무 · 「근처 다른 곳 없어?」 ·
「다른 안으로 바꿔 줘」 · 「되돌려 줘」.

★확정 시나리오의 여섯 사건 중 셋(요식-P3 · 요식-P7 · 액-08)은 **고객이 겪거나 물어서**
  시작한다(설계대응 §0). 감시 루프가 못 보는 것이다 — 식당 당일 휴무·매장 재고는
  소스가 없다.

★재요청 둘(v11 §1 접점 · DoD-8/9) — 최고 안 하나를 먼저 적용하고 알린 뒤, 마음에 안
  들면 고객이 **다른 안으로 바꾸거나** **옛 버전으로 되돌린다.** 알림을 승인 요청으로
  쓰지 않기 때문에 이 두 길이 있어야 성립한다.

★이 파일은 **도메인 판단**만 한다. 입구는 `app/presentation/api/trips.py`(구조화된
  신고·재요청)다. `[미구현]` 고객 **자유 문장**을 Case → 분류(`incident_report`·
  `confirm_request`·`adjust_reject`) → 여기로 잇는 배선은 아직 없다.

★고객 신고는 **근거가 고객 문장**이다. 「고객이 휴무라고 알렸다」를 근거로 남기고,
  우리 확인처럼 말하지 않는다(v11 §4-D).

★요청 id 를 원인 칸에 남긴다 — 같은 신고를 두 번 받아 두 번 고치지 않게
  (`TripStore.version_for_request`).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from .itinerary import Item, StaleItinerary, TripStore
from .replan import (SEATING_BUFFER_MIN, WALK_M_PER_MIN, alternate_record, choose,
                     dining_candidates, dining_fits, dining_notice, store_candidates)

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


def _with_request(cause: dict[str, Any], request_id: str | None) -> dict[str, Any]:
    return {**cause, "request_id": request_id} if request_id else cause


def _option_label(item: Item) -> str:
    """이동 항목 제목 「A → B · 수단」에서 수단 부분."""
    return item.title.split(" · ", 1)[1] if " · " in item.title else item.title


def _applied_record(item: Item) -> dict[str, Any]:
    """지금 적용된 항목을 「다른 안」 하나로 적는다 — 바꾼 뒤 되돌아올 수 있게."""
    mobility = item.kind == "mobility"
    return {"key": (item.detail.get("option") if mobility else None)
            or (str(item.place_id) if item.place_id else str(item.item_id)),
            "name": _option_label(item) if mobility else (item.place or {}).get("name", item.title),
            "place_id": None if mobility or item.place_id is None else str(item.place_id),
            "option": item.detail.get("option") if mobility else None,
            "option_label": _option_label(item) if mobility else None,
            "starts_at": item.starts_at.isoformat(),
            "ends_at": item.ends_at.isoformat() if item.ends_at else None,
            "walk_min": None}


def _title_for(item: Item, name: str) -> str:
    if item.kind == "activity":
        return f"{name} 관람"
    if item.kind == "dining":
        return f"{name} 식사"
    if item.kind == "mobility":
        return f"{item.title.split(' · ', 1)[0]} · {name}"
    return name


class TripDesk:
    def __init__(self, *, store: TripStore, connection_factory: Callable[[], Any],
                 check: Callable[..., dict[str, Any]] | None = None) -> None:
        self.store, self._connect = store, connection_factory
        # ★다른 안으로 바꿀 때 활동이면 **그 시각에 다시 점검**한다 — 계산한 뒤로 시간이
        #   흘렀다. 점검기가 없으면(재생 시험 일부) 점검 없이 바꾼다고 결과에 적는다.
        self._check = check

    # ── 요식-P3 — 늦는다 ────────────────────────────────────────
    def report_delay(self, *, trip_id: UUID, at: datetime, minutes: int,
                     message: str, request_id: str | None = None) -> dict[str, Any]:
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
        cause = _with_request({"category": "customer_report", "type": "delay", "minutes": minutes,
                               "message": message, "evidence": "고객 신고"}, request_id)
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
        return self._apply(trip_id, trip["version"], meal, best, alternates, notice)

    # ── 요식-P7 — 도착했더니 휴무 ──────────────────────────────
    def report_closed(self, *, trip_id: UUID, at: datetime, message: str,
                      request_id: str | None = None) -> dict[str, Any]:
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
        cause = _with_request({"category": "customer_report", "type": "closed_today",
                               "message": message, "evidence": "고객 신고 — 현장 안내문"},
                              request_id)
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
        return self._apply(trip_id, trip["version"], meal, best, alternates, notice)

    # ── 액-08 — 품절, 근처 다른 곳? ────────────────────────────
    def ask_nearby_store(self, *, trip_id: UUID, at: datetime, products: list[str],
                         message: str, request_id: str | None = None) -> dict[str, Any]:
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
                "cause": _with_request({"category": "customer_report", "type": "stock_out",
                                        "products": products, "message": message}, request_id)}

    # ── 재요청 ① — 다른 안으로 바꿔 줘 ─────────────────────────
    def swap_alternate(self, *, trip_id: UUID, item_id: UUID, base_version: int,
                       choice: str | None = None, message: str | None = None,
                       request_id: str | None = None) -> dict[str, Any]:
        """적용된 안을 들고 있던 「다른 안」으로 바꾼다. 원래 안은 다시 「다른 안」이 된다.

        ★고객이 **본 버전**(`base_version`)을 기준으로만 바꾼다. 그 사이 일정이 또
          바뀌었으면 `stale` — 고객이 보지 못한 일정 위에 요청을 얹지 않는다.
        """
        with self._connect() as conn:
            trip, items = self.store.latest(conn, trip_id)
            places = {p["place_id"]: p for p in self.store.places(conn)}
        if trip["version"] != base_version:
            return {"status": "stale", "version": trip["version"]}
        current = next((i for i in items if i.item_id == item_id), None)
        if current is None:
            return {"status": "not_found"}
        alternates = list(current.detail.get("alternates") or [])
        if not alternates:
            return {"status": "no_alternate"}
        pick = alternates[0] if choice is None else next(
            (a for a in alternates if a["key"] == choice), None)
        if pick is None:
            return {"status": "unknown_choice", "choices": [a["key"] for a in alternates]}
        starts = datetime.fromisoformat(pick["starts_at"]) if pick.get("starts_at") else current.starts_at
        ends = datetime.fromisoformat(pick["ends_at"]) if pick.get("ends_at") else current.ends_at
        following = next((i for i in items if i.seq > current.seq), None)
        if following and ends and ends > following.starts_at:
            return {"status": "conflicts_next", "next": following.title}
        place = places.get(str(pick["place_id"])) if pick.get("place_id") else None
        if pick.get("place_id") and place is None:
            return {"status": "not_found"}
        rechecked = None
        if place is not None and current.kind == "activity" and self._check is not None:
            # ★트랜잭션 밖에서 부른다 — 바깥 소스를 기다리며 커넥션을 잡지 않는다.
            report = self._check(place=place, starts_at=starts)
            rechecked = report.get("verdict")
            if rechecked != "clear":
                return {"status": "alternate_invalid", "verdict": rechecked, "report": report}
        applied = _applied_record(current)
        remaining = [a for a in alternates if a is not pick] + [applied]
        name = pick.get("option_label") or pick["name"]
        detail = {**current.detail, "alternates": remaining,
                  "other_options": [a["name"] for a in remaining], "customer_requested": True}
        if current.kind == "mobility":
            detail["option"] = pick.get("option") or pick["key"]
        cause = _with_request({"category": "customer_request", "type": "alternate",
                               "from": applied["name"], "to": name, "message": message},
                              request_id)
        text = (f"요청하신 대로 {applied['name']} 대신 {name}(으)로 바꿨습니다"
                f"({starts:%H:%M} 시작).")
        notice = {"text": text, "language": "ko", "causes": [cause],
                  "changed": {"from": applied["name"], "to": name, "at": starts.isoformat()},
                  "other_options": [a["name"] for a in remaining], "replay": False}
        replacement = current.replaced_by(place=place, title=_title_for(current, name),
                                          detail=detail, starts_at=starts, ends_at=ends)
        outcome = self._write(trip_id, base_version, items, {current.item_id: replacement},
                              reason="customer_request", cause=cause, notice=notice)
        if outcome["status"] == "adjusted":
            outcome.update({"to": name, "rechecked": rechecked})
        return outcome

    # ── 재요청 ② — 되돌려 줘 ───────────────────────────────────
    def rollback(self, *, trip_id: UUID, base_version: int, to_version: int,
                 message: str | None = None, request_id: str | None = None) -> dict[str, Any]:
        """옛 버전의 항목을 **새 버전으로 다시 쓴다**(append-only — 옛 버전을 지우지 않는다).

        ★되살린 항목은 `customer_pinned` 로 표시한다. 감시 루프가 다음 틱에 같은 원인으로
          다시 바꾸면 되돌림이 무의미해진다 — 고객이 알고 고른 것이다.
        """
        with self._connect() as conn:
            trip, items = self.store.latest(conn, trip_id)
            if trip["version"] != base_version:
                return {"status": "stale", "version": trip["version"]}
            if not 1 <= to_version < trip["version"]:
                return {"status": "invalid_version", "version": trip["version"]}
            old = self.store.items(conn, trip_id, to_version)
        current_ids = {i.item_id for i in items}
        restored = []
        for item in old:
            if item.item_id not in current_ids:
                item.detail = {**item.detail, "customer_pinned": True}
                restored.append(item.title)
        cause = _with_request({"category": "customer_request", "type": "rollback",
                               "to_version": to_version, "message": message}, request_id)
        text = f"요청하신 대로 일정을 버전 {to_version} 상태로 되돌렸습니다."
        if restored:
            text += " 되돌린 항목: " + ", ".join(restored) + "."
        notice = {"text": text, "language": "ko", "causes": [cause],
                  "changed": {"rollback_to": to_version, "restored": restored},
                  "other_options": [], "replay": False}
        with self._connect() as conn, conn.transaction():
            try:
                version = self.store.append_version(
                    conn, trip_id=trip_id, base_version=base_version, items=old,
                    reason="rollback", causes=[cause])
            except StaleItinerary:
                return {"status": "stale"}
            self.store.enqueue_notice(conn, trip_id=trip_id, version=version,
                                      payload={**notice, "version": version})
        return {"status": "rolled_back", "version": version, "restored": restored,
                "notice": notice}

    # ── 적용(버전 + 통지를 한 트랜잭션) ─────────────────────────
    def _apply(self, trip_id: UUID, base_version: int, meal: Item, best, alternates,
               notice: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            _, items = self.store.latest(conn, trip_id)
        replacement = meal.replaced_by(
            place=best.place, title=f"{best.name} 식사", starts_at=best.starts_at,
            ends_at=best.ends_at,
            detail={"other_options": notice["other_options"], "customer_reported": True,
                    "alternates": [alternate_record(c) for c in alternates]})
        outcome = self._write(trip_id, base_version, items, {meal.item_id: replacement},
                              reason="customer_report", cause=None, notice=notice)
        if outcome["status"] == "adjusted":
            outcome["to"] = best.name
        return outcome

    def _write(self, trip_id: UUID, base_version: int, items: list[Item],
               replacements: dict[UUID, Item], *, reason: str, cause: dict[str, Any] | None,
               notice: dict[str, Any]) -> dict[str, Any]:
        """★계산에 쓴 버전(`base_version`) 위에만 쓴다. 그 사이 바뀌었으면 `stale`."""
        with self._connect() as conn, conn.transaction():
            new_items = [replacements.get(current.item_id, current) for current in items]
            try:
                version = self.store.append_version(
                    conn, trip_id=trip_id, base_version=base_version, items=new_items,
                    reason=reason, causes=[cause] if cause else notice["causes"])
            except StaleItinerary:
                return {"status": "stale"}
            self.store.enqueue_notice(conn, trip_id=trip_id, version=version,
                                      payload={**notice, "version": version})
        return {"status": "adjusted", "version": version, "notice": notice}


__all__ = ["DINING_RADIUS_M", "TripDesk"]
