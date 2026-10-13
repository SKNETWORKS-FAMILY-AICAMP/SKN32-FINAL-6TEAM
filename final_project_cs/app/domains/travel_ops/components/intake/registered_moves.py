"""검증한 같은 일정 사이의 이동을 등록·기존 여행 경로 조회에 이어 준다."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item
from .moves import selected_context

KST = ZoneInfo("Asia/Seoul")
MODE_IDS = {"walk": "walk", "subway": "subway", "bus": "bus", "transit": "subway_bus", "taxi": "taxi"}


def _stamp(value):
    return datetime.fromisoformat(str(value)).astimezone(KST) if not isinstance(value, datetime) else value.astimezone(KST)


def _xy(place):
    place = place or {}
    return place.get("latitude", place.get("lat")), place.get("longitude", place.get("lon"))


def _match(stop, checked, place):
    """원본 항목 키를 우선하며 옛 여행은 값이 유일하게 일치할 때만 연결한다."""
    meta = (stop.get("detail") or {}).get("intake") or {}
    if "source_id" in meta and (str(meta["source_id"]), meta.get("index")) != (str(checked.get("source_id")), checked.get("index")):
        return False
    start = _stamp(stop["starts_at"])
    end = _stamp(stop["ends_at"]) if stop.get("ends_at") else None
    return (stop["title"] == checked.get("title") and stop["kind"] == checked.get("kind")
            and start.date().isoformat() == checked.get("date") and start.strftime("%H:%M") == checked.get("starts_at")
            and (end.strftime("%H:%M") if end else None) == checked.get("ends_at")
            and _xy(place) == _xy(checked.get("place")) and all(v is not None for v in _xy(place)))


def _moves(stops, review, place_of, *, registration_keys=False):
    if not review:
        return {}
    matched = {}
    for checked in review.get("items") or []:
        matches = [stop for stop in stops if _match(stop, checked, place_of(stop))]
        if len(matches) == 1:
            matched[checked["id"]] = matches[0]
    adjacent = {(id(a), id(b)) for a, b in zip(stops, stops[1:]) if _stamp(a["starts_at"]).date() == _stamp(b["starts_at"]).date()}
    result = {}
    for move in review.get("moves") or []:
        a, b = matched.get(move.get("from")), matched.get(move.get("to"))
        # `[2026-10-13]` 아침 「숙소 → 그날 첫 일정」(`from_stay`)은 순서상 이웃이 아니다 — 그날 첫 일정 **앞**에 싣는다(키 `("before", id(b))`)
        stay_leg = bool(move.get("from_stay"))
        if a is None or b is None or not move.get("depart") or not move.get("arrive") or (
                not stay_leg and (id(a), id(b)) not in adjacent):
            continue
        date = _stamp((b if stay_leg else a)["starts_at"]).date().isoformat()
        depart = datetime.fromisoformat(f"{date}T{move['depart']}").replace(tzinfo=KST)
        arrive = datetime.fromisoformat(f"{date}T{move['arrive']}").replace(tzinfo=KST)
        if arrive < depart:
            continue
        mode = MODE_IDS.get(move.get("mode"))
        context = selected_context(move.get('departure_context'), move.get('selected_option_id'))
        if context is not None and registration_keys:
            # 확인 항목의 position-index 대신 실제 등록 장소 key를 보존한다.
            # 기존 여행 읽기 복구는 place가 없어 원래 문맥을 그대로 둔다.
            for field, stop in (("from_place", a), ("to_place", b)):
                if isinstance(stop.get("place"), str) and isinstance(context.get(field), dict):
                    context[field]["key"] = stop["place"]
        option_id = move['selected_option_id'] if context is not None else mode
        route = {"planned": option_id, "options": [{"id": option_id, "label": move.get("mode_label"),
                 "eta_min": move.get("minutes"), "uses": deepcopy(move.get("uses") or [])}]} if mode else None
        result[("before", id(b)) if stay_leg else id(a)] = {
            "kind": "mobility", "title": (f"{a['title']} → {b['title']}" if stay_leg else move.get("summary") or f"{a['title']} → {b['title']}"),
            "place": None, "starts_at": depart.isoformat(), "ends_at": arrive.isoformat(),
            "detail": {"intake": deepcopy((a.get("detail") or {}).get("intake") or {}),
                       "route_def": route, "route_basis": move.get("basis"),
                       **({"from_stay": True} if stay_leg else {}),
                       **({'departure_context': context} if context is not None else {})}}
    return result


def with_review_moves(body, review):
    """새 등록에 저장된 검증 이동을 추가한다. 원래 등록 몸통은 바꾸지 않는다."""
    body = deepcopy(body)
    stops = body["items"]
    places = {p["key"]: p for p in body.get("places") or []}
    moves = _moves(stops, review, lambda stop: places.get(stop.get("place")),
                   registration_keys=bool((body.get("constraints") or {}).get("taxi_call_product")))
    entries = []
    for stop in stops:
        if ("before", id(stop)) in moves:
            entries.append(moves[("before", id(stop))])      # 아침 「숙소 → 그날 첫 일정」
        entries.append(stop)
        if id(stop) in moves:
            entries.append(moves[id(stop)])
    body["items"] = [{**entry, "seq": seq} for seq, entry in enumerate(entries, 1)]
    return body


def recover_for_routes(items: list[Item], review) -> list[Item]:
    """기존 여행의 누락 이동만 읽기용으로 복구한다. 실제 이동·바뀐 일정은 덮지 않는다."""
    ordered = sorted(items, key=lambda item: item.seq)
    stops = [item for item in ordered if item.kind != "mobility"]
    rows = [{"title": item.title, "kind": item.kind, "starts_at": item.starts_at, "ends_at": item.ends_at,
             "detail": item.detail, "place": item.place, "item_id": item.item_id} for item in stops]
    moves = _moves(rows, review, lambda row: row["place"])
    result = []
    for index, item in enumerate(ordered):
        result.append(item)
        if item.kind == "mobility":
            continue
        at = next(row for row in rows if row["item_id"] == item.item_id)
        move = moves.get(id(at))
        # An explicit mobility item between the stops always wins.
        if move and index + 1 < len(ordered) and ordered[index + 1].kind != "mobility":
            following = ordered[index + 1]
            result.append(Item(item_id=uuid5(NAMESPACE_URL, f"checked-move:{item.item_id}:{following.item_id}"),
                               seq=0, kind="mobility", title=move["title"], place_id=None,
                               starts_at=_stamp(move["starts_at"]), ends_at=_stamp(move["ends_at"]), detail=move["detail"]))
    return [replace(item, seq=seq) for seq, item in enumerate(result, 1)]


def load_trip_review(conn, *, tenant_id, customer_id, trip_id):
    """연결된 본인 접수의 확정 검증 판만 읽는다. 클라이언트의 접수 번호를 신뢰하지 않는다."""
    from . import review

    with conn.cursor() as cur:
        cur.execute("SELECT intake_id, revision FROM trip_intakes WHERE tenant_id=%s AND customer_id=%s "
                    "AND trip_id=%s AND status='confirmed'", (tenant_id, customer_id, trip_id))
        linked = cur.fetchone()
    return review.load(conn, tenant_id, linked[0], linked[1]) if linked else None
