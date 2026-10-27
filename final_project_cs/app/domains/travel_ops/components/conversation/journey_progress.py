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


#: `[2026-10-22 ST4F-716 실서버 확인]` 계산기는 도착 목표에서 거꾸로 센다. 목표를 「지금 출발」에 맞추다 몇 분 빠듯해지면(배차 · 여유 반올림) 계산기는 후보 없음(`arrive_late`)을
#:  돌려준다 — 그때는 목표를 이만큼 늦춰 다시 묻고, 출발이 지금부터 이 안이면 「지금 출발」로 받는다(전에는 바로 실패해 도보 15분 거리도 「확인을 마치지 못했어요」가 됐다)
DEPART_NOW_STEP = timedelta(minutes=5)


def _depart_now(engine, origin, destination, now, deadline):
    """Ask the common calculator again at an arrival goal that starts this leg now."""
    goal = max(deadline, now + timedelta(hours=2))
    for _ in range(4):
        try:
            got, why = engine(origin, destination, goal, now)
        except Exception as exc:
            return None, {"code": "engine_failed", "exception_type": type(exc).__name__}
        if got is None:
            if (why or {}).get("code") == "arrive_late":
                goal += DEPART_NOW_STEP
                continue
            return None, why
        delta = now - got["starts_at"]
        if abs(delta.total_seconds()) < 60 or timedelta(0) <= -delta <= DEPART_NOW_STEP:
            return {**got, "visit_starts_at": goal}, None
        goal += delta
    return None, {"code": "departure_not_now"}


#: `[2026-10-22 사용자 결정 — ST4F-716]` 운영시간 위반 — 앞당긴 다음 방문에 **새로** 생기면 시각을 바꾸지 않고 이유를 알린다(겹침 · 이동 부족은 지금처럼 `needs_replan`)
HOURS_CODES = frozenset({"closed_day", "before_opening", "after_closing", "after_last_entry", "break_time",
                         "outside_hours", "dining_closed_at_slot"})
_HOURS_WHY = {"closed_day": "그날 쉬는 날이라", "before_opening": "아직 문을 열지 않아", "break_time": "브레이크 타임에 걸려",
              "after_closing": "문 닫는 시각과 맞지 않아", "after_last_entry": "입장 마감 시각과 맞지 않아"}


def _known(facts) -> bool:
    return bool(facts.known or facts.activity or facts.open_at_slot is not None)


def _judged(item: Item, facts) -> Item:
    """판정에만 쓰는 사본 — 운영시간 사실(`intake/hours.py` `facts_for`)을 장소에 얹는다. 저장하는 항목은 그대로다."""
    place = dict(item.place or {})
    place["attributes"] = {**(place.get("attributes") or {}), **facts.attributes}
    if facts.activity:
        place["activity"] = facts.activity
    if facts.open_at_slot is not None:
        place["ledger"] = {"open_at_slot": facts.open_at_slot}
    return replace(item, place=place)


def _opening(facts, start: datetime) -> datetime | None:
    """새 시작이 그날 여는 시각보다 이르면 그 여는 시각 — 요일표(`place_hours.hours_on`)를 모르면 None."""
    from app.domains.travel_ops.components.places.place_hours import hours_on

    local = start.astimezone(KST)
    today = hours_on(facts.attributes, local.date())
    if today is None or today == "closed" or local.time() >= today.opens:
        return None
    return datetime.combine(local.date(), today.opens, tzinfo=KST)


def hours_reader(connect, tenant_id: str):
    """`[2026-10-22 ST4F-716]` 수정 모드 「다시 제출」과 같은 운영시간 사실(`facts_for` — DB 만 읽는다). 부를 때마다 짧은 연결을 쓴다(트랜잭션 밖)."""
    from app.domains.travel_ops.components.intake.hours import facts_for

    def read(item: Item, start: datetime, end: datetime | None):
        with connect() as conn:
            return facts_for(conn, tenant_id, item.place, item.kind, start, end)
    return read


def plan(*, trip: dict, items: list[Item], action: str, target: Item | None,
         now: datetime, engine=None, hours=None) -> tuple[list[Item], dict]:
    """Compute one progress change. Customer facts and deferred navigation stay explicit.

    `hours(item, start, end)` `[2026-10-22 ST4F-716]` — 운영시간 사실을 읽는 함수(`hours_reader`). 주면 `advance_trip` 이 다음 방문을 앞당기기 전에
    원래 · 새 시각의 운영시간을 판정에 넣고, 여는 시각 전이면 여는 시각으로 맞춘다. 없으면 저장된 장소 속성만 본다(전과 같다)."""
    # `[2026-10-22 사용자 결정 — ST4F-716]` 일정 이름 뒤 조사는 받침에 맞춰 고른다(전에는 「을(를)」 · 「(으)로」를 그대로 보였다)
    from app.domains.travel_ops.components.intake.review import eul, eun, iga, ro

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
        return items, {"status": "already_applied", "text": f"{eun(target.title)} 이미 완료했어요."}
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
            "status": "adjusted", "text": f"{eul(target.title)} {now:%H:%M}에 완료한 것으로 반영했어요.",
            "item_id": str(target.item_id), "state": "completed"}
    following = next((i for i in stops if i.seq > target.seq and not terminal(i)
                      and i.starts_at.astimezone(KST).date() == now.date()), None)
    if following is None:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{eul(target.title)} 완료했어요. 오늘 남은 방문 일정은 없어요."}
    if any(i.kind == "mobility" and target.seq < i.seq < following.seq
           and (i.detail.get("execution") or {}).get("state") == "departing" for i in ordered):
        return items, {"status": "already_applied", "text": f"{ro(following.title)} 이미 이동을 시작한 일정이에요."}
    if following.locked or following.booking_id:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{eun(target.title)} 완료했어요. 다음 {eun(following.title)} 고정·예약 시각을 유지했어요.",
            "navigation": "fixed_time_preserved"}
    a, b = _place(target), _place(following)
    if a is None or b is None:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{eun(target.title)} 완료했어요. {ro(following.title)} 지금 출발할 길을 계산하려면 현재 위치가 필요해요.",
            "navigation": "needs_location"}
    engine = _planner(trip, engine)
    got, why = _depart_now(engine, a, b, now, following.starts_at) if engine else (None, {"code": "engine_unavailable"})
    if got is None:
        return [changed.get(i.item_id, i) for i in ordered], {
            "status": "adjusted", "text": f"{eun(target.title)} 완료했어요. {ro(following.title)} 지금 출발할 이동 계산은 확인을 마치지 못했어요.",
            "navigation": "unverifiable", "navigation_reason": why}
    duration = (following.ends_at - following.starts_at) if following.ends_at else timedelta(hours=1)
    visit_start = got["visit_starts_at"] + rounding_slack
    # ★`[2026-10-22 사용자 결정 — ST4F-716]` 앞당기기 전에 「다시 제출」과 같은 운영시간 사실을 원래 · 새 시각으로 읽어 판정에 넣는다.
    #   새 시작이 여는 시각보다 이르면 여는 시각으로 맞추고, 그래도 원래보다 이르지 않으면 앞당기지 않는다. 못 읽으면 그 판정만 빼고 그렇다고 남긴다
    judged_before, facts_now, hours_check, opened = following, None, None, None
    if hours is not None:
        try:
            facts_was = hours(following, following.starts_at, following.ends_at)
            facts_now = hours(following, visit_start, visit_start + duration)
            opens = _opening(facts_now, visit_start)
            if opens is not None:
                if opens >= following.starts_at:
                    return [changed.get(i.item_id, i) for i in ordered], {
                        "status": "adjusted", "text": f"{eun(target.title)} 완료했어요. {eun(following.title)} {opens:%H:%M}에 문을 열어 시각은 그대로 두었어요.",
                        "navigation": "opens_later", "hours_check": "checked"}
                visit_start = opened = opens
                facts_now = hours(following, visit_start, visit_start + duration)
            judged_before = _judged(following, facts_was)
            hours_check = "checked" if _known(facts_now) else "unknown"
        except Exception as exc:
            log.warning("progress hours check failed (%s)", type(exc).__name__)
            judged_before, facts_now, hours_check, opened = following, None, "unavailable", None
            visit_start = got["visit_starts_at"] + rounding_slack
    noted = {"hours_check": hours_check} if hours_check else {}
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
    # 판정에만 운영시간을 얹은 사본으로 본다 — 원래 시각에도 있던 위반은 이 변경의 탓이 아니다(`introduced_violations`)
    before = [judged_before if i.item_id == following.item_id else i for i in ordered]
    checked = [_judged(i, facts_now) if facts_now is not None and i.item_id == following.item_id else i for i in after]
    problems = introduced_violations(trip, before, checked)
    if problems:
        kept = [changed.get(i.item_id, i) if i.item_id == target.item_id else i for i in ordered]
        hours_problems = [p for p in problems if p.code in HOURS_CODES]
        if hours_problems:
            why = _HOURS_WHY.get(hours_problems[0].code, "그 시각에 운영하지 않아")
            return kept, {"status": "adjusted", "text": f"{eun(target.title)} 완료했어요. 지금 가면 {iga(following.title)} {why} 이동 시각은 바꾸지 않았어요.",
                          "navigation": "hours_conflict", "navigation_reason": [p.reason for p in problems], **noted}
        return kept, {
            "status": "adjusted", "text": f"{eun(target.title)} 완료했어요. 지금 이동하면 뒤 일정과 맞지 않아 이동 시각은 바꾸지 않았어요.",
            "navigation": "needs_replan", "navigation_reason": [p.reason for p in problems], **noted}
    # 여는 시각으로 맞춘 앞당김은 그렇다고 말한다(목업 `tripilot-trip-now-done.html` 「문 열기 전에 닿을 때」)
    said = (f"{eul(target.title)} {now:%H:%M}에 마쳤어요. {eun(following.title)} {opened:%H:%M}에 문을 열어 {opened:%H:%M} 시작으로 앞당겼어요."
            if opened is not None else
            f"{eul(target.title)} {now:%H:%M}에 마쳤고, 지금 {ro(following.title)} 이동해요. 예상 도착은 {got['ends_at']:%H:%M}예요.")
    return after, {"status": "adjusted", "text": said,
                   "departure_at": got["starts_at"].isoformat(), "arrival_at": got["ends_at"].isoformat(),
                   "next_start_at": visit_start.isoformat(),
                   "route": got["route"], "state": "departing", **noted}


def _record(store, conn, *, trip_id, base_version, key, decision, original, after, outcome, now, message, target):
    """진행 결과를 새 판 하나 · 알림 하나로 쓴다. 기준 판은 `append_version` 이 다시 확인한다(낡았으면 `StaleItinerary`)."""
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


def apply(*, store, connect, trip_id, base_version, decision, now, request_id, message, destination=None, hours=None):
    """`_apply` 를 저장소 운영 실패 확인으로 감싼다 — `[2026-10-27 C 전수검사]` 판 그대로가 확인될 때만 escalated · save_failed(전에는 일반 500)."""
    from .storage_failure import guarded

    return guarded(lambda: _apply(store=store, connect=connect, trip_id=trip_id, base_version=base_version,
                                  decision=decision, now=now, request_id=request_id, message=message,
                                  destination=destination, hours=hours),
                   connect=connect, tenant=store.tenant_id, trip_id=trip_id, base_version=base_version,
                   where="journey progress")


def _apply(*, store, connect, trip_id, base_version, decision, now, request_id, message, destination=None, hours=None):
    """Version, actual progress and notice are saved by the canonical store transaction.

    ★`[2026-10-22 사용자 결정 — ST4F-716]` 도착(`arrive_item`) 밖의 진행은 이동 계산 · 운영시간 확인을 **트랜잭션 밖에서** 하고, 저장 트랜잭션에서
    같은 요청 · 기준 판을 다시 본다 — 깊은 경로 탐색(몇 초 × 최대 4번) 동안 트랜잭션을 열어 두지 않는다. 다른 장소 도착은 장소 행을 먼저 써서 한 트랜잭션 그대로다.
    `hours` 를 안 주면 `hours_reader`(「다시 제출」과 같은 운영시간 사실)를 쓴다."""
    key = "progress:" + request_id
    if decision.action != "arrive_item":
        with connect() as conn:
            already = store.version_for_request(conn, trip_id, key)
            trip, items = (None, None) if already is not None else store.latest(conn, trip_id)
        if already is not None:
            return {"status": "already_applied", "version": already, "text": "같은 진행 요청은 이미 반영했어요."}
        if trip["version"] != base_version:
            raise StaleItinerary("progress itinerary changed")
        after, outcome = plan(trip=trip, items=items, action=decision.action, target=decision.item, now=now,
                              hours=hours if hours is not None else hours_reader(connect, store.tenant_id))
        with connect() as conn, conn.transaction():
            already = store.version_for_request(conn, trip_id, key)
            if already is not None:
                return {"status": "already_applied", "version": already, "text": "같은 진행 요청은 이미 반영했어요."}
            return _record(store, conn, trip_id=trip_id, base_version=base_version, key=key, decision=decision,
                           original=list(items), after=after, outcome=outcome, now=now, message=message, target=decision.item)
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
        return _record(store, conn, trip_id=trip_id, base_version=base_version, key=key, decision=decision,
                       original=original, after=after, outcome=outcome, now=now, message=message, target=target)
