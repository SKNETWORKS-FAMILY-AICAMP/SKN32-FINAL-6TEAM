"""Apply customer-reported travel progress through the shared itinerary version store."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item, StaleItinerary
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.components.itinerary.itinerary_checks import STAY_KINDS

log = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
ACTIONS = ("arrive_item", "complete_item", "advance_trip", "finish_day")
TERMINAL = frozenset({"completed", "skipped"})


def terminal(item: Item) -> bool:
    return (item.detail.get("execution") or {}).get("state") in TERMINAL


def _reported(item: Item, state: str, now: datetime, *, preserve_past=False) -> Item:
    detail = deepcopy(item.detail)
    detail["execution"] = {**detail.get("execution", {}), "state": state,
                           "reported_at": now.isoformat(), "source": "customer_report"}
    if state == "arrived":
        detail["execution"]["actual_start"] = now.isoformat()
        if item.kind in STAY_KINDS or item.kind == "flight" or item.booking_id or item.locked:
            return replace(item, detail=detail)
        duration = (item.ends_at - item.starts_at) if item.ends_at else timedelta(hours=1)
        return replace(item, starts_at=now, ends_at=now + duration, detail=detail)
    if state == "completed":
        now = min(now, item.ends_at) if preserve_past and item.ends_at and item.ends_at < now else now
        detail["execution"]["actual_end"] = now.isoformat()
        if item.starts_at >= now:
            detail["execution"]["start_unknown"] = True
        if item.kind in STAY_KINDS or item.kind == "flight" or item.booking_id or item.locked:
            return replace(item, detail=detail)
        return replace(item, starts_at=min(item.starts_at, now), ends_at=now, detail=detail)
    return replace(item, detail=detail)


def _place(item: Item) -> dict | None:
    if not item.place or item.place.get("latitude") is None or item.place.get("longitude") is None:
        return None
    return {"key": str(item.place_id or item.item_id), "name": item.place["name"],
            "lat": item.place["latitude"], "lon": item.place["longitude"]}


def arrival_anchor(items, target, fix, now):
    """Use a reported position before the unvisited replacement's planned position."""
    if fix is not None:
        from .trip_here import assess
        if assess(fix,now=now)[0]:
            return fix.lat,fix.lon
    located = [i for i in items if i.kind != "mobility" and _place(i) is not None
               and i.starts_at.astimezone(KST).date()==now.astimezone(KST).date()]
    reported = [i for i in located if (i.detail.get("execution") or {}).get("state") in ("arrived","completed")]
    previous = [i for i in located if target is not None and i.seq<target.seq]
    basis = max(reported,key=lambda i:i.seq) if reported else (max(previous,key=lambda i:i.seq) if previous else target)
    if basis is None or _place(basis) is None:
        return None
    return float(basis.place["latitude"]),float(basis.place["longitude"])


def _planner(trip, supplied=None):
    if supplied is not None:
        return supplied
    try:
        return legs.leg_planner(trip.get("party_size"), trip.get("constraints") or {}, stage="pre_departure")
    except Exception as exc:
        log.warning("progress navigation setup failed (%s)", type(exc).__name__)
        return None  # The caller records navigation unavailability without rejecting a reported fact.


def _depart_now(engine, origin, destination, now, deadline):
    """Ask the common calculator again at an arrival goal that starts this leg now."""
    goal = max(deadline, now + timedelta(hours=2))
    for _ in range(4):
        try:
            got, why = engine(origin, destination, goal, now)
        except Exception as exc:
            return None, {"code": "engine_failed", "exception_type": type(exc).__name__}
        if got is None:
            return None, why
        delta = now - got["starts_at"]
        if abs(delta.total_seconds()) < 60:
            return {**got, "visit_starts_at": goal}, None
        goal += delta
    return None, {"code": "departure_not_now"}


def plan(*, trip: dict, items: list[Item], action: str, target: Item | None,
         now: datetime, engine=None) -> tuple[list[Item], dict]:
    """Compute one progress change. Customer facts and deferred navigation stay explicit."""
    received_now = now.astimezone(KST)
    now = received_now.replace(second=0, microsecond=0)
    rounding_slack = timedelta(minutes=1) if received_now > now else timedelta(0)
    ordered = sorted(items, key=lambda i: i.seq)
    stops = [i for i in ordered if i.kind != "mobility"]
    today = [i for i in stops if i.starts_at.astimezone(KST).date() == now.date()]
    if action not in ACTIONS:
        raise ValueError("unsupported_progress_action")
    if target is not None:
        target = next((i for i in stops if i.item_id == target.item_id), None)
        if target is None:
            raise ValueError("progress_target_not_current")
    if target is None and action != "finish_day":
        active = [i for i in today if not terminal(i) and i.starts_at <= now < (i.ends_at or now + timedelta(seconds=1))]
        if len(active) == 1:
            target = active[0]
        else:
            arrived = [i for i in today if (i.detail.get("execution") or {}).get("state") == "arrived"]
            if len(arrived) == 1:
                target = arrived[0]
    if action != "finish_day" and target is None:
        return items, {"status": "clarify", "text": "어느 방문을 마쳤거나 도착했는지 장소 이름을 알려 주세요."}
    changed = {}
    if action == "finish_day":
        for item in today:
            if terminal(item) or item.kind in STAY_KINDS:
                continue
            reported_visited = target is not None and target in today and item.seq <= target.seq
            state = "completed" if reported_visited or item.starts_at <= now else "skipped"
            changed[item.item_id] = _reported(item, state, now, preserve_past=True)
        for item in ordered:
            if item.kind == "mobility" and item.starts_at.astimezone(KST).date() == now.date() and not terminal(item):
                changed[item.item_id] = _reported(item, "completed" if item.ends_at and item.ends_at <= now else "skipped", now, preserve_past=True)
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": "오늘 일정을 종료했어요. 오늘의 남은 출발 안내도 종료했어요.",
            "day": now.date().isoformat(), "state": "completed"}
    if terminal(target) and not (action == "advance_trip" and (target.detail.get("execution") or {}).get("state") == "completed"):
        return items, {"status": "already_applied", "text": f"{target.title}은(는) 이미 완료했어요."}
    if action == "arrive_item" and (target.detail.get("execution") or {}).get("state") == "arrived":
        return items, {"status": "already_applied", "text": f"{target.title}에 이미 도착한 것으로 반영돼 있어요."}
    changed[target.item_id] = target if terminal(target) else _reported(target, "arrived" if action == "arrive_item" else "completed", now)
    if action == "arrive_item":
        # Arrival proves the preceding visit is over; retain that visit instead of deleting it.
        for previous in today:
            if previous.seq < target.seq and not terminal(previous):
                changed[previous.item_id] = _reported(previous, "completed", now, preserve_past=True)
        after = [changed.get(i.item_id, i) for i in ordered]
        # A route into an already visited destination must not emit a fresh departure notice.
        after = [(_reported(i, "completed", now, preserve_past=True) if i.kind == "mobility" and i.seq < target.seq
                  and not terminal(i) else i) for i in after]
        following = next((i for i in stops if i.seq > target.seq and not terminal(i)
                          and i.starts_at.astimezone(KST).date() == now.date()), None)
        navigation = None
        if following is not None:
            after = [i for i in after if not (i.kind == "mobility" and target.seq < i.seq < following.seq and not terminal(i))]
            current = changed[target.item_id]
            a, b, planner = _place(current), _place(following), _planner(trip, engine)
            got = None
            why = {"code": "location_or_engine_unavailable"}
            if a and b and planner:
                try:
                    got, why = planner(a, b, following.starts_at, current.ends_at or now)
                except Exception as exc:
                    why = {"code": "engine_failed", "exception_type": type(exc).__name__}
            if got is not None:
                after.append(Item(uuid4(), target.seq + 1, "mobility", f"{a['name']} → {b['name']}", None,
                    got["starts_at"], got["ends_at"], detail={"route_def": got["route"], "route_basis": "rejudged",
                    "departure_context": got.get("departure_context")}))
            else:
                navigation = {"navigation": "needs_location" if not a or not b else "unverifiable", "navigation_reason": why}
            after.sort(key=lambda i: (i.seq, i.kind != "mobility"))
            after = [replace(i, seq=n) for n, i in enumerate(after, 1)]
        return after, {"status": "adjusted", "text": f"{target.title}에 도착한 것으로 반영했어요. 도착 시각은 {now:%H:%M}예요."
                          + (" 다음 이동은 위치·경로 확인이 필요해요." if navigation else ""),
                       "item_id": str(target.item_id), "state": "arrived", **(navigation or {})}
    if action == "complete_item":
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{target.title}을(를) {now:%H:%M}에 완료한 것으로 반영했어요.",
            "item_id": str(target.item_id), "state": "completed"}
    following = next((i for i in stops if i.seq > target.seq and not terminal(i)
                      and i.starts_at.astimezone(KST).date() == now.date()), None)
    if following is None:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{target.title}을(를) 완료했어요. 오늘 남은 방문 일정은 없어요."}
    if any(i.kind == "mobility" and target.seq < i.seq < following.seq
           and (i.detail.get("execution") or {}).get("state") == "departing" for i in ordered):
        return items, {"status": "already_applied", "text": f"{following.title}(으)로 이미 이동을 시작한 일정이에요."}
    if following.locked or following.booking_id:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{target.title}은(는) 완료했어요. 다음 {following.title}은(는) 고정·예약 시각을 유지했어요.",
            "navigation": "fixed_time_preserved"}
    a, b = _place(target), _place(following)
    if a is None or b is None:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{target.title}은(는) 완료했어요. {following.title}으로 지금 출발할 길을 계산하려면 현재 위치가 필요해요.",
            "navigation": "needs_location"}
    engine = _planner(trip, engine)
    got, why = _depart_now(engine, a, b, now, following.starts_at) if engine else (None, {"code": "engine_unavailable"})
    if got is None:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{target.title}은(는) 완료했어요. {following.title}으로 지금 출발할 이동 계산은 확인을 마치지 못했어요.",
            "navigation": "unverifiable", "navigation_reason": why}
    duration = (following.ends_at - following.starts_at) if following.ends_at else timedelta(hours=1)
    visit_start = got["visit_starts_at"] + rounding_slack
    changed[following.item_id] = replace(following, starts_at=visit_start, ends_at=visit_start + duration)
    route = Item(uuid4(), target.seq + 1, "mobility", f"{a['name']} → {b['name']}", None,
                 got["starts_at"], got["ends_at"], detail={"route_def": got["route"], "route_basis": "rejudged",
                 "departure_context": got.get("departure_context"), "execution": {"state": "departing", "source": "customer_request"}})
    # Drop the superseded connecting leg, including a future leg at the old scheduled time.
    after = [changed.get(i.item_id, i) for i in ordered
             if not (i.kind == "mobility" and target.seq < i.seq < following.seq)] + [route]
    # Preserve the declared visit order. Clock sorting can put a later stop ahead
    # of the destination and hide an overlap from the shared checker.
    after.sort(key=lambda i: (i.seq, i.kind != "mobility"))
    after = [replace(i, seq=n) for n, i in enumerate(after, 1)]
    from app.domains.travel_ops.components.actions.itinerary_actions import introduced_violations
    problems = introduced_violations(trip, ordered, after)
    if problems:
        return [changed.get(i.item_id, i) if i.item_id == target.item_id else i for i in ordered], {
            "status": "adjusted", "text": f"{target.title}은(는) 완료했어요. 지금 이동하면 뒤 일정과 맞지 않아 이동 시각은 바꾸지 않았어요.",
            "navigation": "needs_replan", "navigation_reason": [p.reason for p in problems]}
    return after, {"status": "adjusted", "text": f"{target.title}을(를) {now:%H:%M}에 마쳤고, 지금 {following.title}(으)로 이동해요. 예상 도착은 {got['ends_at']:%H:%M}예요.",
                   "departure_at": got["starts_at"].isoformat(), "arrival_at": got["ends_at"].isoformat(),
                   "next_start_at": visit_start.isoformat(),
                   "route": got["route"], "state": "departing"}


def apply(*, store, connect, trip_id, base_version, decision, now, request_id, message, destination=None):
    """Version, actual progress and notice are saved by the canonical store transaction."""
    key = "progress:" + request_id
    with connect() as conn, conn.transaction():
        already = store.version_for_request(conn, trip_id, key)
        if already is not None:
            return {"status": "already_applied", "version": already, "text": "같은 진행 요청은 이미 반영했어요."}
        trip, items = store.latest(conn, trip_id)
        if trip["version"] != base_version:
            raise StaleItinerary("progress itinerary changed")
        original = list(items)
        target = decision.item
        requested = str((decision.raw or {}).get("destination_text") or "").strip()
        if decision.action == "arrive_item" and requested and target is not None:
            from app.domains.travel_ops.components.intake.reopen_commit import store_place
            target = next((i for i in items if i.item_id == target.item_id), None)
            if target is None:
                raise StaleItinerary("arrival target changed")
            if ((target.booking_id or target.locked or target.detail.get("booking") or target.detail.get("customer_pinned"))
                    and requested not in (target.title, (target.place or {}).get("name"))):
                return {"status": "edit_refused", "text": "예약·고정 일정의 장소는 그대로 두었어요. 실제 방문한 다른 곳을 별도 일정으로 기록할지 알려 주세요."}
            previous_id = target.item_id
            if destination is not None:
                attributes = {"source": destination.method, "reported_by": "customer",
                              **({"dining_place_uid": destination.dining_place_uid} if destination.dining_place_uid else {})}
                with conn.cursor() as cur:
                    place_id = store_place(conn, cur, store.tenant_id, trip_id, name=destination.name,
                        kind=destination.kind or target.kind, lat=destination.latitude, lon=destination.longitude,
                        weather_sensitive=None, attributes=attributes)
                place = {"place_id": str(place_id), "name": destination.name, "kind": destination.kind or target.kind,
                         "latitude": destination.latitude, "longitude": destination.longitude, "attributes": attributes}
                target = replace(target, place_id=place_id, place=place, title=destination.name)
            else:
                target = replace(target, place_id=None, place=None, title=requested,
                    detail={**target.detail, "requested_place": {"name": requested, "status": "unresolved", "source": "customer_report"}})
            previous = next(i for i in original if i.item_id == previous_id)
            old_name = (previous.place or {}).get("name") or previous.title
            new_name = (target.place or {}).get("name") or target.title
            if new_name != old_name:
                prior_visit = max((i.seq for i in items if i.kind != "mobility" and i.seq < target.seq), default=0)
                items = [_reported(i, "skipped", now) if i.kind == "mobility" and prior_visit < i.seq < target.seq
                         and not terminal(i) else i for i in items]
                target = replace(target, item_id=uuid4(), replaces_item_id=previous_id)
            if new_name != old_name and target.detail.get("execution"):
                detail = deepcopy(target.detail)
                detail["execution_history"] = [*detail.get("execution_history", []), detail.pop("execution")]
                target = replace(target, detail=detail)
            items = [target if i.item_id == previous_id else i for i in items]
        after, outcome = plan(trip=trip, items=items, action=decision.action, target=target, now=now)
        if outcome.get("navigation") and target is not None:
            after = [replace(i, detail={**i.detail, "navigation": {"status": outcome["navigation"],
                "reason": outcome.get("navigation_reason"), "checked_at": now.isoformat()}})
                if i.item_id == target.item_id else i for i in after]
        if after == original:
            return outcome
        cause = {"category": "customer_request", "type": "progress", "request_id": key,
                 "message": message[:200], "action": decision.action, "reported_at": now.isoformat()}
        version = store.append_version(conn, trip_id=trip_id, base_version=base_version, items=after,
                                       reason="customer_report", causes=[cause])
        store.enqueue_notice(conn, trip_id=trip_id, version=version, payload={
            "text": outcome["text"], "version": version, "causes": [cause], "changed": {"progress": decision.action},
            "language": "ko", "replay": False})
    return {**outcome, "version": version}
