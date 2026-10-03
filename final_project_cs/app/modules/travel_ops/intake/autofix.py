# -*- coding: utf-8 -*-
"""**전체 자동 추천** — 확인이 필요한 일정을 한 번에, 운영시간 · 휴무 · 앞뒤 이동까지 맞춰 보고 바꾼다. `[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업 시나리오 7]`

★목업: 「확인 필요 장소는 후보 1순위부터 운영시간 · 휴무 · 앞뒤 이동을 맞춰 보고 맞는 첫 곳으로, 늦게 닿는 구간은 시각을 앞뒤 이동에 맞춰 줄인다.
  고정한 일정은 건드리지 않는다.」 그리고 적용은 **검증을 끝낸 것만** — 맞는 안이 없으면 지어내지 않고 그대로 두고 이유를 말한다.

순서(일차별, 시각 순 — 앞 일정이 바뀌면 그 바뀐 값이 다음 일정의 기준이 된다):
    ① 고정한 일정은 기준으로만 쓴다(바꾸지 않는다)
    ② 손볼 일정 = 확인 필요 장소(status review) + 앞 일정에서 늦게 닿는 일정
    ③ 장소가 문제면 후보를 차례로(지금 곳이 이름 모호함뿐이면 지금 곳이 먼저) — 운영시간 · 휴무를 통과하는 첫 곳
    ④ 그 곳에서 **시각**을 맞춘다: 시작 = 앞 일정이 끝난 뒤 이동해 닿는 시각(5분 올림), 끝 = 다음 일정에 닿도록 줄임(5분 내림), 30분 미만이면 못 맞춘 것
    ⑤ 맞으면 바꿀 값(장소 · 시각)을 모으고 다음 일정으로 — 맞는 곳이 없으면 그대로 두고 이유를 적는다
바꿀 값은 `edits` 로 한 번에 새 판이 된다(`pipeline.autofix`) — 고객이 직접 고른 것과 같은 길이라 되돌리기(앞 값으로 다시 `edits`)도 같다.
★`[2026-10-03 ui 세션 요청서 「장소 해석 개선」]` **예약했다고 적힌 일정은 바꾸지 않는다**(`kept: booked`) — 장소도 시각도. 예약한 식당을 다른 곳으로 바꾸자고 하던 것(실서버 실측: 「성수 예약 식당 → 랩포터리」)을 막는다.
  이름 없는 줄(`needs_choice`)은 후보 중 같은 종류 · 지역 안의 곳으로 채운다(`candidates.py`).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Callable

from . import candidates as cand_module
from .hours import facts_for
from .moves import leg_between
from .review import KST, _Budgeted, _dt, default_engine, public_place

MIN_STAY_MIN = 30           #: 머무는 시간이 이보다 짧아지면 못 맞춘 것 — 목업의 「최소 30분」
#: 맞는 곳을 찾으려고 차례로 시간표로 맞춰 보는 후보 수의 상한 — 화면에 보이는 셋(`candidates.LIMIT`)보다 넓다: 순위는 싼 판정(어림 이동)이라 앞 셋이 시간표로는
#: 안 맞고 넷째가 맞을 수 있다. ★우리가 고른 값 — 후보 하나를 맞추는 데 계산기 3~5번이 든다(상한 `ENGINE_BUDGET_S` 가 총량을 막는다)
CANDIDATES_TRIED = 8
ROUND_MIN = 5
ENGINE_BUDGET_S = 20.0


def _ceil5(moment: datetime) -> datetime:
    minutes = moment.hour * 60 + moment.minute + (1 if moment.second or moment.microsecond else 0)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=math.ceil(minutes / ROUND_MIN) * ROUND_MIN)


def _floor5(moment: datetime) -> datetime:
    minutes = moment.hour * 60 + moment.minute
    return moment.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=(minutes // ROUND_MIN) * ROUND_MIN)


def _hhmm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def _pt(place: dict[str, Any], key: str) -> dict[str, Any]:
    return {"key": key, "name": place["name"], "lat": float(place["latitude"]), "lon": float(place["longitude"])}


def earliest_start(engine: Any, prev_place: dict[str, Any], place: dict[str, Any], prev_end: datetime) -> datetime | None:
    """앞 일정이 끝난 뒤 떠나 이 곳에 **시간표로 확인되게** 닿는 가장 이른 시작(5분 올림). 계산기 답이 모자라면 몇 번 다시 맞춰 본다 — 끝내 못 맞추면 None(맞춘 척하지 않는다)."""
    start = prev_end + timedelta(minutes=1)
    for _ in range(4):
        leg = leg_between(engine, _pt(prev_place, "prev"), _pt(place, "cand"), prev_end, start, deep=False)
        if leg.ok:
            return _ceil5(start)
        if leg.slack_min < 0:
            shift = -leg.slack_min
        elif leg.latest_depart is not None:                 # 늦지는 않지만 시간표로 확인이 안 됨 — 가장 늦은 출발이 앞 일정 끝에 닿을 만큼 미룬다
            shift = math.ceil((prev_end - leg.latest_depart).total_seconds() / 60)
        else:
            shift = 5
        # ★시간표는 편 사이가 띄엄띄엄이라 1분씩 미루면 수렴하지 않는다(2026-10-03 실서버: 11:52 → 11:53 → 11:54 … 끝내 실패) — 한 번에 최소 5분
        start = start + timedelta(minutes=max(shift, 5))
    leg = leg_between(engine, _pt(prev_place, "prev"), _pt(place, "cand"), prev_end, start, deep=False)
    return _ceil5(start) if leg.ok else None


def latest_end(engine: Any, place: dict[str, Any], next_place: dict[str, Any], next_start: datetime) -> datetime | None:
    """이 곳에서 늦게 나서도 다음 일정에 **시간표로 확인되게** 닿는 가장 늦은 끝(5분 내림). 끝내 못 맞추면 None."""
    end = next_start - timedelta(minutes=1)
    for _ in range(4):
        leg = leg_between(engine, _pt(place, "cand"), _pt(next_place, "next"), end, next_start, deep=False)
        if leg.ok:
            return _floor5(end)
        if leg.slack_min < 0:
            shift = -leg.slack_min
        elif leg.latest_depart is not None:
            shift = math.ceil((end - leg.latest_depart).total_seconds() / 60)
        else:
            shift = 5
        end = end - timedelta(minutes=max(shift, 5))
    leg = leg_between(engine, _pt(place, "cand"), _pt(next_place, "next"), end, next_start, deep=False)
    return _floor5(end) if leg.ok else None


def plan(conn, *, tenant_id: str, review: dict[str, Any], kakao: Any = None, engine: Callable[..., Any] | None = None,
         use_engine: bool = True, now: datetime | None = None) -> dict[str, Any]:
    """검증을 끝낸 대체 일정. `{changes:[{id, source_id, index, title, from, to, reason, edits}], kept:[{id, title, reason}]}`.
    DB 에 쓰지 않는다 — 적용은 부르는 쪽이 `edits` 로 한다."""
    if engine is None and use_engine:
        engine = default_engine(None)
    budget = _Budgeted(engine, ENGINE_BUDGET_S) if engine is not None else None
    # 바꾸는 동안의 기준 상태 — 앞 일정이 바뀌면 그 값으로 다음 일정을 맞춘다
    items = [{**it, "rows": list(it["rows"])} for it in review["items"]]
    late_into = {m["to"] for m in review["moves"] if m["status"] == "review"}
    changes: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    last_changed = -2
    for i, item in enumerate(items):
        placed_bad = item["status"] == "review"
        late = item["id"] in late_into
        if not placed_bad and not late and last_changed == i - 1 and item["date"] and item["starts_at"]:
            # 바로 앞 일정이 바뀌었다 — 그 바뀐 값으로 이 일정에 아직 닿는지 다시 본다(처음 검사에는 없던 늦음이 생길 수 있다)
            before = next((x for x in reversed(items[:i]) if x["date"] == item["date"] and x["place"]), None)
            if before and item["place"]:
                before_end = _dt(before["date"], before["ends_at"] or before["starts_at"])
                this_start = _dt(item["date"], item["starts_at"])
                if before_end is not None and this_start is not None:
                    leg = leg_between(budget, _pt(before["place"], "prev"), _pt(item["place"], "cand"), before_end, this_start, deep=False)
                    late = not leg.ok
        if not placed_bad and not late:
            continue
        if item["locked"]:
            kept.append({"id": item["id"], "title": item["title"], "reason": "locked"})
            continue
        if item.get("booked") is True:
            kept.append({"id": item["id"], "title": item["title"], "reason": "booked"})
            continue
        if not item["date"] or not item["starts_at"]:
            kept.append({"id": item["id"], "title": item["title"], "reason": "no_time"})
            continue
        prev = next((x for x in reversed(items[:i]) if x["date"] == item["date"] and x["place"]), None)
        nxt = next((x for x in items[i + 1:] if x["date"] == item["date"] and x["place"]), None)
        start, end = _dt(item["date"], item["starts_at"]), _dt(item["date"], item["ends_at"] or item["starts_at"])
        duration = max(end - start, timedelta(minutes=MIN_STAY_MIN))
        # 후보 장소: 장소 문제가 없으면 지금 곳 하나. 문제면 (이름 모호함뿐이면 지금 곳 먼저) + 대체 후보
        places: list[dict[str, Any]] = []
        place_problem = any(r["row"] in ("place", "hours", "closed") and r["result"] in ("bad", "warn") for r in item["rows"])
        # 운영시간만 어긋난 곳(쉬는 날 · 장소 문제는 아님)은 지금 곳에서 시각을 옮겨 먼저 맞춰 본다
        hours_problem = any(r["row"] in ("hours", "closed") and r["result"] in ("warn", "bad") for r in item["rows"])
        hours_only = place_problem and item["place_state"] in ("found", "customer") and not any(
            r["result"] == "bad" for r in item["rows"] if r["row"] in ("place", "closed"))
        if item["place"] and (not place_problem or item["place_state"] == "picked_nearest" or hours_only):
            places.append({**item["place"], "ref": None})
        if place_problem:
            alt = cand_module.alternatives(conn, tenant_id=tenant_id, review={"items": items, "moves": review["moves"]},
                                           item=item, kakao=kakao, engine=budget, use_engine=False, now=now, rank_only=True,
                                           limit=CANDIDATES_TRIED)
            places += [c["place"] for c in alt["candidates"] if c["status"] != "bad"]
        done = None
        failed: set[str] = set()
        for place in places:
            fit = _fit_window(conn, tenant_id, item, place, prev, nxt, start, duration, budget, require_known=hours_problem)
            if isinstance(fit, str):
                failed.add(fit)
                continue
            done = (place, fit)
            break
        if done is None:
            # 후보 자체가 없었던 것 · 운영시간(쉬는 날 · 닫는 시간 · 운영시간 미확인)에 안 맞은 것 · 앞뒤 이동에 못 맞춘 것을 **실제 실패 원인으로** 구별해 말한다.
            # 이동이 한 번이라도 원인이면 `no_fitting_time`(시각을 바꾸면 될 수 있다), 운영시간만이면 `no_fitting_place`
            reason = ("no_candidates" if not places else "no_fitting_time" if failed & {"travel", "stay"} else "no_fitting_place")
            kept.append({"id": item["id"], "title": item["title"], "reason": reason})
            continue
        place, (new_start, new_end, hours_known) = done
        before = {"place": public_place(item["place"]), "starts_at": item["starts_at"], "ends_at": item["ends_at"]}
        same_place = (bool(item["place"]) and item["place"]["name"] == place["name"]
                      and abs(float(item["place"]["latitude"]) - float(place["latitude"])) < 1e-6
                      and abs(float(item["place"]["longitude"]) - float(place["longitude"])) < 1e-6)
        changed_place = not same_place or item["place_state"] in ("picked_nearest",)
        edits: list[dict[str, Any]] = []
        if changed_place:
            edits.append({"field": "place", "value": _pick(place, item)})
        if _hhmm(new_start) != item["starts_at"]:
            edits.append({"field": "starts_at", "value": _hhmm(new_start)})
        if _hhmm(new_end) != (item["ends_at"] or ""):
            edits.append({"field": "ends_at", "value": _hhmm(new_end)})
        if not edits:
            kept.append({"id": item["id"], "title": item["title"], "reason": "nothing_to_change"})
            continue
        after = {"place": {k: place.get(k) for k in ("name", "latitude", "longitude", "source")},
                 "starts_at": _hhmm(new_start), "ends_at": _hhmm(new_end)}
        changes.append({"id": item["id"], "source_id": item["source_id"], "index": item["index"], "title": item["title"],
                        "from": before, "to": after,
                        "reason": ("place_and_time" if changed_place and len(edits) > 1 else "place" if changed_place else "time"),
                        # 운영시간을 확인했나 — 모르는 곳은 장소 문제(이름 모호함 · 늦음)를 푸는 추천에는 쓰이지만 「열려 있다」고 하지 않는다(결과 줄에 `unknown`)
                        "hours_known": hours_known, "edits": edits})
        last_changed = i
        # 다음 일정을 맞출 기준을 갱신한다
        items[i] = {**item, "place": after["place"], "starts_at": after["starts_at"], "ends_at": after["ends_at"],
                    "place_state": "customer", "status": "adjusted"}
    return {"changes": changes, "kept": kept}


def _pick(place: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """고객이 직접 고른 것과 같은 값 모양(`pipeline._checked_pick`)."""
    origin = {"tour_api": "tour_api", "kakao": "kakao", "places": "places"}.get(str(place.get("source")), "search")
    out = {"name": place["name"], "latitude": place["latitude"], "longitude": place["longitude"],
           "source": "customer_pick", "origin": origin}
    kind = place.get("kind") or item.get("kind")
    if kind in ("activity", "dining"):
        out["kind"] = kind
    if place.get("category"):
        out["category"] = str(place["category"])[:60]
    if place.get("content_id"):
        out["content_id"] = str(place["content_id"])
    return out


def _fit_window(conn, tenant_id: str, item: dict[str, Any], place: dict[str, Any], prev: dict[str, Any] | None,
                nxt: dict[str, Any] | None, start: datetime, duration: timedelta,
                engine: Any, *, require_known: bool = False) -> tuple[datetime, datetime, bool] | str:
    """이 곳에서 앞 · 뒤 일정에 닿으면서 운영시간 안에 드는 (시작, 끝). 못 맞추면 None.

    운영시간이 어긋나면 먼저 **시각을 옮겨** 본다 — 열기 전이면 여는 시각으로 미루고, 닫는 시각을 넘으면 거기까지로 줄인다(머무는 시간이 30분 이상 남아야 한다).
    쉬는 날 · 입장 마감 · 브레이크 타임은 시각을 옮겨도 못 맞추므로 그 곳은 안 된다(다른 후보로).
    성공은 `(시작, 끝, 운영시간을 확인했나)`, 실패는 원인 글자 — `travel` 앞뒤 이동에 못 맞춤 · `stay` 머무는 시간이 모자람 · `hours` 운영시간에 안 맞음/미확인."""
    from datetime import datetime as _datetime

    from ..itinerary_checks import Part, check_itinerary
    from ..place_hours import DayHours, hours_on

    earliest = start
    if prev and prev["place"]:
        prev_end = _dt(prev["date"], prev["ends_at"] or prev["starts_at"])
        if prev_end is not None:
            arrive = earliest_start(engine, prev["place"], place, prev_end)
            if arrive is None:
                return "travel"                              # 앞 일정에서 이 곳에 닿는 시각을 못 맞춘다 — 이 후보는 안 된다
            earliest = max(start, arrive)
    latest: datetime | None = None
    if nxt and nxt["place"]:
        next_start = _dt(nxt["date"], nxt["starts_at"])
        if next_start is not None:
            latest = latest_end(engine, place, nxt["place"], next_start)
            if latest is None:
                return "travel"                              # 이 곳에서 다음 일정에 닿는 끝을 못 맞춘다
    new_start = earliest
    for _ in range(3):
        new_end = new_start + duration
        if latest is not None and new_end > latest:
            new_end = latest
        if new_end - new_start < timedelta(minutes=MIN_STAY_MIN) or new_end.date() != new_start.date():
            return "stay"
        facts = facts_for(conn, tenant_id, place, item["kind"], new_start, new_end)
        if not facts.known:
            # 운영시간 문제를 풀려는 추천이면 운영시간을 모르는 곳은 「맞는 곳」이 아니다(검증을 끝낸 것만 적용한다)
            return "hours" if require_known else (new_start, new_end, False)
        vios = check_itinerary([Part(seq=1, kind=item["kind"], title=place["name"], starts_at=new_start, ends_at=new_end,
                                     place={"name": place["name"], "attributes": dict(facts.attributes)})])
        if not vios:
            return new_start, new_end, True
        today = hours_on(facts.attributes, new_start.date())
        codes = {v.code for v in vios}
        if not isinstance(today, DayHours) or codes - {"before_opening", "after_closing"}:
            return "hours"
        if "before_opening" in codes:
            opens = _datetime.combine(new_start.date(), today.opens, tzinfo=KST)
            if opens > new_start:
                new_start = _ceil5(opens)
        if "after_closing" in codes:
            closes = _datetime.combine(new_start.date(), today.closes, tzinfo=KST)
            latest = closes if latest is None else min(latest, closes)
    return "hours"


__all__ = ["MIN_STAY_MIN", "earliest_start", "latest_end", "plan"]
