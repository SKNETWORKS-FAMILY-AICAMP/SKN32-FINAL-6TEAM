# -*- coding: utf-8 -*-
"""일정을 **어떻게 바꿀지 계산만** 한다 — DB 도 바깥 소스도 부르지 않는다.

★왜 뺐나(`[결정 2026-09-17]`). 이 계산은 두 곳이 쓴다.

    시나리오용 여행 버전   trip_watch.py(감시) · trip_desk.py(신고·재요청)  → 계산 후 직접 쓴다
    Case 버전             activity · dining · mobility Team               → 계산 후 제안으로 낸다

  두 벌로 두면 문구와 판단이 조용히 갈린다(RULE §3.3 — 같은 기능의 두 구현 금지).
  그래서 계산은 여기 하나만 두고, 읽기와 쓰기는 부르는 쪽이 한다.
  옮기기 전 원본: `legacy/final_project_cs/app/modules/travel_ops/trip_desk.py`·`trip_watch.py`.

★입력은 **이미 읽은 값**이다(항목·장소·점검 결과). 점검을 다시 해야 하는 자리(대안 재검증)만
  `check` 콜러블을 받는다 — 시나리오 버전은 점검기를 직접, Team 은 읽기 도구를 넣는다.

★결과는 둘 중 하나다.
    ItineraryChange  새 일정 버전으로 쓸 것(바꾼 항목 · 원인 · 통지)
    NoChange         바꾸지 않는 이유(status 는 옮기기 전 반환값과 같은 문자열)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from .itinerary import Item
from .replan import (SEATING_BUFFER_MIN, WALK_M_PER_MIN, activity_candidates, alternate_record,
                     change_notice, choose, dining_candidates, dining_fits, dining_notice,
                     route_candidates, route_notice, store_candidates)

#: 대안 식당을 찾는 반경(미터). ★우리가 고른 값이다 — 도보 약 9분.
DINING_RADIUS_M = 700


@dataclass
class ItineraryChange:
    """새 일정 버전 하나. `replacements` 는 바뀌는 항목만, `full_items` 는 되돌림처럼 통째로 쓸 때."""

    reason: str
    causes: list[dict[str, Any]]
    notice: dict[str, Any]
    replacements: dict[UUID, Item] = field(default_factory=dict)
    full_items: list[Item] | None = None
    summary: dict[str, Any] = field(default_factory=dict)

    def new_items(self, current: list[Item]) -> list[Item]:
        if self.full_items is not None:
            return list(self.full_items)
        return [self.replacements.get(item.item_id, item) for item in current]


@dataclass
class NoChange:
    status: str
    detail: dict[str, Any] = field(default_factory=dict)


Plan = ItineraryChange | NoChange


# ── 작은 도우미 ────────────────────────────────────────────────
def minutes_between(start: datetime, end: datetime | None, default: int = 60) -> int:
    return default if end is None else int((end - start).total_seconds() // 60)


def object_particle(word: str) -> str:
    """을/를. 마지막 글자가 한글이 아니면 「을(를)」로 둔다 — 틀리게 붙이지 않는다."""
    last = word.strip()[-1:] if word.strip() else ""
    if not ("가" <= last <= "힣"):
        return "을(를)"
    return "을" if (ord(last) - 0xAC00) % 28 else "를"


def round_up_5(moment: datetime) -> datetime:
    extra = (-moment.minute) % 5
    return (moment + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def with_request(cause: dict[str, Any], request_id: str | None) -> dict[str, Any]:
    return {**cause, "request_id": request_id} if request_id else cause


def option_label(item: Item) -> str:
    """이동 항목 제목 「A → B · 수단」에서 수단 부분."""
    return item.title.split(" · ", 1)[1] if " · " in item.title else item.title


def applied_record(item: Item) -> dict[str, Any]:
    """지금 적용된 항목을 「다른 안」 하나로 적는다 — 바꾼 뒤 되돌아올 수 있게."""
    mobility = item.kind == "mobility"
    return {"key": (item.detail.get("option") if mobility else None)
            or (str(item.place_id) if item.place_id else str(item.item_id)),
            "name": option_label(item) if mobility else (item.place or {}).get("name", item.title),
            "place_id": None if mobility or item.place_id is None else str(item.place_id),
            "option": item.detail.get("option") if mobility else None,
            "option_label": option_label(item) if mobility else None,
            "starts_at": item.starts_at.isoformat(),
            "ends_at": item.ends_at.isoformat() if item.ends_at else None,
            "walk_min": None}


def title_for(item: Item, name: str) -> str:
    if item.kind == "activity":
        return f"{name} 관람"
    if item.kind == "dining":
        return f"{name} 식사"
    if item.kind == "mobility":
        return f"{item.title.split(' · ', 1)[0]} · {name}"
    return name


def next_after(items: list[Item], item: Item) -> Item | None:
    later = [other for other in items if other.seq > item.seq]
    return min(later, key=lambda other: other.seq) if later else None


# ── 감시 — 활동 ────────────────────────────────────────────────
def plan_activity_adjustment(*, item: Item, report: dict[str, Any], places: list[dict[str, Any]],
                             check: Callable[..., dict[str, Any]], now: datetime) -> Plan:
    """성립 점검이 `disrupted` 인 활동 항목 — 대안 후보 → 탈락·재검증·사전식 비교로 **하나**."""
    causes = report.get("disruptions", [])
    candidates = activity_candidates(original=item.place, places=places,
                                     start=item.starts_at, end=item.ends_at, causes=causes)
    best, alternates, rejected = choose(
        candidates, lambda c: check(place=c.place, starts_at=item.starts_at))
    if best is None:
        # ★못 풀면 부분 반영하지 않는다(§6-C-5). 사람에게 넘길 재료를 남긴다.
        return NoChange("unresolved", {"causes": causes,
                                       "rejected": {c.name: c.rejected for c in rejected}})
    replay = any(cause.get("mode") == "replay" for cause in causes)
    notice = change_notice(original=item.place, replacement=best.place,
                           start=item.starts_at, causes=causes,
                           alternates=alternates, replay=replay)
    replacement = item.replaced_by(
        place=best.place, title=f"{best.place['name']} 관람",
        detail={"auto_adjusted_at": now.isoformat(),
                "other_options": notice["other_options"],
                "alternates": [alternate_record(c) for c in alternates]})
    return ItineraryChange(reason="auto_adjusted", causes=causes, notice=notice,
                           replacements={item.item_id: replacement},
                           summary={"from": item.place["name"], "to": best.place["name"]})


# ── 감시 — 이동 ────────────────────────────────────────────────
def route_of(item: Item, routes: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """★경로 정의는 항목이 들고 온다(`route_def`). 밖에서 준 `routes` 가 있으면 그것이 먼저다."""
    return (routes or {}).get(str(item.detail.get("route"))) or item.detail.get("route_def")


def route_targets(route: dict[str, Any]) -> list[str]:
    return sorted({target for option in route["options"] for target in option.get("uses", [])})


def planned_option(item: Item, route: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    options = {option["id"]: option for option in route["options"]}
    chosen = str(item.detail.get("option") or route["planned"])
    return chosen, options.get(chosen, {})


def plan_route_adjustment(*, item: Item, following: Item | None, route: dict[str, Any],
                          events: dict[str, Any], now: datetime) -> Plan:
    """계획한 수단이 쓰는 구간에 사건이 걸렸으면 경로를 다시 고른다. 안 걸렸으면 `clear`."""
    chosen, planned = planned_option(item, route)
    hit = {target: events[target] for target in planned.get("uses", []) if target in events}
    if not hit:
        return NoChange("clear")
    causes = [{"category": "route_event", "target": target, **event}
              for target, event in hit.items()]
    candidates = route_candidates(
        route={**route, "planned": chosen}, depart=item.starts_at,
        planned_arrival=item.ends_at or item.starts_at,
        next_start=following.starts_at if following else None, events=events)
    best, alternates, rejected = choose(candidates)
    if best is None:
        return NoChange("unresolved", {"causes": causes,
                                       "rejected": {c.name: c.rejected for c in rejected}})
    replay = any(cause.get("mode") == "replay" for cause in causes)
    notice = route_notice(route={**route, "planned": chosen}, planned=planned, best=best,
                          alternates=alternates, rejected=rejected, causes=causes,
                          planned_arrival=item.ends_at or item.starts_at,
                          next_title=following.title if following else None, replay=replay)
    replacement = item.replaced_by(
        place=None, title=f"{route['from']} → {route['to']} · {(best.option or {}).get('label')}",
        starts_at=best.starts_at, ends_at=best.ends_at,
        detail={**item.detail, "option": best.key,
                "auto_adjusted_at": now.isoformat(),
                "other_options": notice["other_options"],
                "alternates": [alternate_record(c) for c in alternates]})
    return ItineraryChange(reason="auto_adjusted", causes=causes, notice=notice,
                           replacements={item.item_id: replacement},
                           summary={"from": planned.get("label"),
                                    "to": (best.option or {}).get("label")})


# ── 고객 신고 — 식당 ───────────────────────────────────────────
def _dining_change(meal: Item, best, alternates, notice: dict[str, Any], *,
                   reason: str = "customer_report") -> ItineraryChange:
    replacement = meal.replaced_by(
        place=best.place, title=f"{best.name} 식사", starts_at=best.starts_at,
        ends_at=best.ends_at,
        detail={"other_options": notice["other_options"],
                **({"customer_reported": True} if reason == "customer_report" else {}),
                "alternates": [alternate_record(c) for c in alternates]})
    return ItineraryChange(reason=reason, causes=notice["causes"], notice=notice,
                           replacements={meal.item_id: replacement}, summary={"to": best.name})


def plan_delay(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]],
               at: datetime, minutes: int, message: str, request_id: str | None) -> Plan:
    """「N분 늦는다」. 다음 식사 항목이 그 도착 시각에 성립하는지 보고, 안 되면 바꾼다."""
    meal = next((i for i in items if i.kind == "dining" and i.starts_at >= at), None)
    if meal is None or meal.place is None:
        return NoChange("no_meal", {"message": "늦어지는 시각 뒤에 식사 일정이 없다"})
    arrival = meal.starts_at + timedelta(minutes=minutes)
    duration = minutes_between(meal.starts_at, meal.ends_at)
    fits, why = dining_fits(meal.place, arrival, duration)
    cause = with_request({"category": "customer_report", "type": "delay", "minutes": minutes,
                          "message": message, "evidence": "고객 신고"}, request_id)
    if fits is True:
        return NoChange("still_fits", {"arrival": arrival.isoformat()})
    following = next((i for i in items if i.seq > meal.seq), None)
    candidates = dining_candidates(
        original=meal.place, places=places, arrival=arrival, minutes=duration,
        constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
        next_start=following.starts_at if following else None)
    best, alternates, rejected = choose(candidates)
    if best is None:
        return NoChange("unresolved", {"reason": why,
                                       "rejected": {c.name: c.rejected for c in rejected}})
    notice = dining_notice(
        original=meal.place, best=best, alternates=alternates,
        reason=f"점심 도착이 {arrival:%H:%M}(으)로 늦어져 {meal.place['name']}은 {why}",
        cause=cause, after=None, constraint_note="브레이크타임 없는")
    return _dining_change(meal, best, alternates, notice)


def plan_closed(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]],
                at: datetime, message: str, request_id: str | None) -> Plan:
    """「오늘 임시휴무」. 지금 식사 항목을 걸어갈 수 있는 대체 식당으로 바꾼다."""
    meal = next((i for i in items if i.kind == "dining"
                 and i.starts_at <= at < (i.ends_at or i.starts_at + timedelta(hours=1))), None)
    if meal is None or meal.place is None:
        return NoChange("no_meal", {"message": "지금 시각에 식사 일정이 없다"})
    duration = minutes_between(meal.starts_at, meal.ends_at)
    following = next((i for i in items if i.seq > meal.seq), None)
    cause = with_request({"category": "customer_report", "type": "closed_today",
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
        arrival = round_up_5(at + timedelta(minutes=walk + SEATING_BUFFER_MIN))
        candidates += dining_candidates(
            original=meal.place, places=[place], arrival=arrival, minutes=duration,
            constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
            next_start=following.starts_at if following else None)
    best, alternates, rejected = choose(candidates)
    if best is None:
        return NoChange("unresolved", {"rejected": {c.name: c.rejected for c in rejected}})
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
    return _dining_change(meal, best, alternates, notice)


# ── 새벽 확인 — 그날 그 시각에 안 연다 (D-020, 2026-09-25) ──────────
def plan_closed_on_day(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]],
                       meal: Item, source: str, detail: str, checked_at: datetime,
                       exclude: set[str] = frozenset()) -> Plan:
    """새벽 확인에서 **계획한 시각에 안 여는** 식당 — 같은 시각에 근처 대체 식당으로 바꾼다.

    ★고객 신고(`plan_closed`)와 다르다 — 그쪽은 고객이 **지금 가게 앞에** 있어 걸어갈 시간만큼 입장을
      뒤로 민다. 여기는 새벽이라 고객이 아직 나서지 않았다 → **계획한 입장 시각 그대로** 찾는다.
    ★근거는 바깥 소스의 판정이다(고객 문장이 아니다). 원인에 소스와 확인 시각을 남긴다.
    """
    if meal.place is None:
        return NoChange("no_meal", {"message": "장소가 없는 식사 일정이다"})
    duration = minutes_between(meal.starts_at, meal.ends_at)
    following = next((i for i in items if i.seq > meal.seq and i.kind != "mobility"), None)
    cause = {"category": "place_closed", "type": "closed_on_day", "source": source,
             "checked_at": checked_at.isoformat(), "detail": detail,
             "evidence": f"{source} 새벽 확인 — {detail}"}
    candidates = dining_candidates(
        original=meal.place, places=places, arrival=meal.starts_at, minutes=duration,
        constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
        next_start=following.starts_at if following else None, exclude=set(exclude))
    best, alternates, rejected = choose(candidates)
    if best is None:
        return NoChange("unresolved", {"causes": [cause],
                                       "rejected": {c.name: c.rejected for c in rejected}})
    payment = (trip.get("constraints") or {}).get("payment")
    notice = dining_notice(
        original=meal.place, best=best, alternates=alternates,
        reason=(f"{meal.place['name']}이(가) {meal.starts_at:%m월 %d일 %H:%M}에 영업하지 않는 것으로 "
                f"새벽에 확인했습니다({detail})"),
        cause=cause, after=None,
        constraint_note="카드 결제가 가능한" if payment == "card" else None)
    return _dining_change(meal, best, alternates, notice, reason="auto_adjusted")


# ── 고객 신고 — 품절(일정은 안 바꾼다) ─────────────────────────
def plan_nearby_store(*, items: list[Item], places: list[dict[str, Any]], at: datetime,
                      products: list[str], message: str, request_id: str | None) -> dict[str, Any]:
    """품절 상품을 **취급할 만한** 매장을 귀가 동선에서 고른다. 일정은 안 바꾼다.

    ★재고는 확인하지 않는다 — 재고 소스가 없다(§7-C 3단계). 그래서 답에
      `[미확인]` 을 붙인다. 「있다」고 말하지 않는다.
    """
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
            f"{listed}{object_particle(listed)} 취급하는 매장이지만 지금 재고는 확인하지 "
            f"못했습니다[미확인].")
    return {"status": "answered", "text": text, "recommendation": best.name,
            "stock": "unverified", "other_options": [c.name for c in alternates],
            "rejected": {c.name: c.rejected for c in rejected},
            "cause": with_request({"category": "customer_report", "type": "stock_out",
                                   "products": products, "message": message}, request_id)}


# ── 재요청 ① — 다른 안으로 ─────────────────────────────────────
def plan_swap(*, trip_version: int, base_version: int, items: list[Item],
              places_by_id: dict[str, dict[str, Any]], item_id: UUID, choice: str | None,
              message: str | None, request_id: str | None,
              check: Callable[..., dict[str, Any]] | None) -> Plan:
    """적용된 안을 들고 있던 「다른 안」으로 바꾼다. 원래 안은 다시 「다른 안」이 된다.

    ★고객이 **본 버전**(`base_version`)을 기준으로만 바꾼다. 그 사이 일정이 또
      바뀌었으면 `stale` — 고객이 보지 못한 일정 위에 요청을 얹지 않는다.
    """
    if trip_version != base_version:
        return NoChange("stale", {"version": trip_version})
    current = next((i for i in items if i.item_id == item_id), None)
    if current is None:
        return NoChange("not_found")
    alternates = list(current.detail.get("alternates") or [])
    if not alternates:
        return NoChange("no_alternate")
    pick = alternates[0] if choice is None else next(
        (a for a in alternates if a["key"] == choice), None)
    if pick is None:
        return NoChange("unknown_choice", {"choices": [a["key"] for a in alternates]})
    starts = datetime.fromisoformat(pick["starts_at"]) if pick.get("starts_at") else current.starts_at
    ends = datetime.fromisoformat(pick["ends_at"]) if pick.get("ends_at") else current.ends_at
    following = next((i for i in items if i.seq > current.seq), None)
    if following and ends and ends > following.starts_at:
        return NoChange("conflicts_next", {"next": following.title})
    place = places_by_id.get(str(pick["place_id"])) if pick.get("place_id") else None
    if pick.get("place_id") and place is None:
        return NoChange("not_found")
    rechecked = None
    if place is not None and current.kind == "activity" and check is not None:
        # ★계산한 뒤로 시간이 흘렀다 — 그 시각에 다시 점검한다.
        report = check(place=place, starts_at=starts)
        rechecked = (report or {}).get("verdict")
        if rechecked != "clear":
            return NoChange("alternate_invalid", {"verdict": rechecked, "report": report})
    applied = applied_record(current)
    remaining = [a for a in alternates if a is not pick] + [applied]
    name = pick.get("option_label") or pick["name"]
    detail = {**current.detail, "alternates": remaining,
              "other_options": [a["name"] for a in remaining], "customer_requested": True}
    if current.kind == "mobility":
        detail["option"] = pick.get("option") or pick["key"]
    cause = with_request({"category": "customer_request", "type": "alternate",
                          "from": applied["name"], "to": name, "message": message},
                         request_id)
    text = (f"요청하신 대로 {applied['name']} 대신 {name}(으)로 바꿨습니다"
            f"({starts:%H:%M} 시작).")
    notice = {"text": text, "language": "ko", "causes": [cause],
              "changed": {"from": applied["name"], "to": name, "at": starts.isoformat()},
              "other_options": [a["name"] for a in remaining], "replay": False}
    replacement = current.replaced_by(place=place, title=title_for(current, name),
                                      detail=detail, starts_at=starts, ends_at=ends)
    return ItineraryChange(reason="customer_request", causes=[cause], notice=notice,
                           replacements={current.item_id: replacement},
                           summary={"to": name, "rechecked": rechecked})


# ── 재요청 ② — 되돌려 줘 ───────────────────────────────────────
def plan_rollback(*, trip_version: int, base_version: int, current_items: list[Item],
                  old_items: list[Item], to_version: int, message: str | None,
                  request_id: str | None) -> Plan:
    """옛 버전의 항목을 **새 버전으로 다시 쓴다**(append-only — 옛 버전을 지우지 않는다).

    ★되살린 항목은 `customer_pinned` 로 표시한다. 감시 루프가 다음 틱에 같은 원인으로
      다시 바꾸면 되돌림이 무의미해진다 — 고객이 알고 고른 것이다.
    """
    if trip_version != base_version:
        return NoChange("stale", {"version": trip_version})
    if not 1 <= to_version < trip_version:
        return NoChange("invalid_version", {"version": trip_version})
    current_ids = {i.item_id for i in current_items}
    restored = []
    for item in old_items:
        if item.item_id not in current_ids:
            item.detail = {**item.detail, "customer_pinned": True}
            restored.append(item.title)
    cause = with_request({"category": "customer_request", "type": "rollback",
                          "to_version": to_version, "message": message}, request_id)
    text = f"요청하신 대로 일정을 버전 {to_version} 상태로 되돌렸습니다."
    if restored:
        text += " 되돌린 항목: " + ", ".join(restored) + "."
    notice = {"text": text, "language": "ko", "causes": [cause],
              "changed": {"rollback_to": to_version, "restored": restored},
              "other_options": [], "replay": False}
    return ItineraryChange(reason="rollback", causes=[cause], notice=notice,
                           full_items=list(old_items), summary={"restored": restored})


__all__ = ["DINING_RADIUS_M", "ItineraryChange", "NoChange", "Plan", "applied_record",
           "minutes_between", "next_after", "object_particle", "plan_activity_adjustment",
           "plan_closed", "plan_closed_on_day", "plan_delay", "plan_nearby_store", "plan_rollback",
           "plan_route_adjustment", "plan_swap", "planned_option", "route_of", "route_targets",
           "title_for", "with_request"]
