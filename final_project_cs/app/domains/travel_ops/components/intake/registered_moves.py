"""검증한 같은 일정 사이의 이동을 등록·기존 여행 경로 조회에 이어 준다."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from uuid import NAMESPACE_URL, uuid4, uuid5
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


def _entry(a, b, move, *, registration_keys=False):
    """검증한 이동 하나 → 이동 항목 모양(`fill_edited_moves` 용 — `_moves` 의 이웃 구간 갈래와 같은 규칙). 출발 · 도착이 없거나 거꾸로면 None."""
    if not move.get("depart") or not move.get("arrive"):
        return None
    date = _stamp(a["starts_at"]).date().isoformat()
    depart = datetime.fromisoformat(f"{date}T{move['depart']}").replace(tzinfo=KST)
    arrive = datetime.fromisoformat(f"{date}T{move['arrive']}").replace(tzinfo=KST)
    if arrive < depart:
        return None
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
    return {"kind": "mobility", "title": move.get("summary") or f"{a['title']} → {b['title']}",
            "place": None, "starts_at": depart.isoformat(), "ends_at": arrive.isoformat(),
            "detail": {"intake": deepcopy((a.get("detail") or {}).get("intake") or {}),
                       "route_def": route, "route_basis": move.get("basis"),
                       **({'departure_context': context} if context is not None else {})}}


def fill_edited_moves(items: list[Item], review, keys: dict, customer_pairs=frozenset(),
                      fixed_ids=frozenset()) -> tuple[list[Item], list[str]]:
    """`[2026-10-14]` 수정 접수 「완료」 — 확인 화면이 검증한 이동을 새 판에 잇는다. → (새 판 일정, 수단을 바꾼 구간 이름들).

    `keys` = 새 판 일정 id → 접수의 (원본, 항목 번호). 같은 날 이웃한 두 일정이 둘 다 접수 항목일 때
    - 사이에 이동 항목이 없으면(바뀐 일정 옆 · 새로 이웃이 된 구간) 검증한 이동을 넣는다 — 출발 알림이 이 항목으로 나간다(`trip_reminders`)
    - 고객이 **이 접수에서** 수단을 골랐거나 「추천으로」 되돌렸으면(`customer_pairs` = `review.customer_mode_pairs`) 옛 이동을 검증한 이동으로 갈음한다(`replaces_item_id`).
      ★`[2026-10-14]` 처음엔 `mode_choice.state=kept` 로 갈랐는데, 여행에서 가져온 수단(`method: trip`)도 kept 라 「완료」 때마다 모든 이동이 「바뀜」이 됐다
    - 그 밖에는 옛 이동을 그대로 둔다(계획 때의 경로 · 출발 문맥을 지운 검증값으로 덮지 않는다)
    ☆처음 판(팀원 커밋 6eb2ad44)은 바뀐 일정 옆 이동을 빼기만 하고 다시 넣지 않아, 그 구간 출발 알림이 사라지고 고른 수단도 저장되지 않았다.
    ★`[2026-10-15 ST4F-490]` `fixed_ids` = 접수에 넣지 않은 **고정 일정**(여행 일정 id 문자열). 재검사가 「고정 ↔ 접수 일정」 구간과 아침 「고정 숙소 → 그날 첫 일정」
      구간(`from_stay`)도 세므로(구간의 고정 쪽 id 가 여행 일정 id) 그 구간도 같은 규칙으로 넣는다. ☆전에는 양쪽이 다 접수 항목일 때만 넣어 항공 · 지난 일정 ·
      숙소 옆 이동이 사라졌다(Codex 검토 2026-10-14 ②)."""
    if not review:
        return items, []
    ids = {(str(c.get("source_id")), c.get("index")): c.get("id") for c in review.get("items") or []}

    def review_id(item: Item):
        """검사가 이 일정을 부르는 id — 접수 항목은 「0-3」, 고정 일정은 여행 일정 id."""
        key = keys.get(item.item_id)
        if key:
            return ids.get(key)
        return str(item.item_id) if str(item.item_id) in fixed_ids else None

    moves = {(m.get("from"), m.get("to")): m for m in review.get("moves") or [] if not m.get("from_stay")}
    # 아침 「숙소 → 그날 첫 일정」(`from_stay`) — 이웃 사이가 아니라 그날 첫 일정 **앞**에 넣는다(뒤 일정 id 로 찾는다)
    stay_moves = {m.get("to"): m for m in review.get("moves") or [] if m.get("from_stay")}
    titles = {str(item.item_id): item.title for item in items}
    ordered = sorted(items, key=lambda item: item.seq)
    stop_at = [n for n, item in enumerate(ordered) if item.kind != "mobility"]
    out: list[Item] = list(ordered[:stop_at[0]]) if stop_at else list(ordered)
    picked: list[str] = []
    for k, n in enumerate(stop_at):
        a = ordered[n]
        stay = stay_moves.get(review_id(a))
        day = a.starts_at.astimezone(KST).date()
        if stay is not None and not (out and out[-1].kind == "mobility" and out[-1].starts_at.astimezone(KST).date() == day):
            hotel = titles.get(str(stay.get("from"))) or ""
            entry = _entry({"title": hotel, "starts_at": a.starts_at, "detail": a.detail}, {"title": a.title}, stay)
            if entry is not None:
                out.append(Item(item_id=uuid4(), seq=0, kind="mobility", title=f"{hotel} → {a.title}" if hotel else entry["title"],
                                place_id=None, starts_at=_stamp(entry["starts_at"]), ends_at=_stamp(entry["ends_at"]),
                                detail={**entry["detail"], "from_stay": True}))
        out.append(a)
        end = stop_at[k + 1] if k + 1 < len(stop_at) else len(ordered)
        between = ordered[n + 1:end]
        if k + 1 >= len(stop_at):
            out += between
            continue
        b = ordered[end]
        pair = (review_id(a), review_id(b))
        move = moves.get(pair) if pair[0] and pair[1] else None
        same_day = a.starts_at.astimezone(KST).date() == b.starts_at.astimezone(KST).date()
        entry = None
        if move is not None and same_day and (not between or f"{pair[0]}~{pair[1]}" in customer_pairs):
            entry = _entry({"title": a.title, "starts_at": a.starts_at, "detail": a.detail},
                           {"title": b.title}, move)
        if entry is None:
            out += between
            continue
        old = next((i for i in between if i.kind == "mobility"), None)
        if old is not None:
            picked.append(f"{a.title} → {b.title} 이동({move.get('mode_label') or move.get('mode')})")
        out.append(Item(item_id=uuid4(), seq=0, kind="mobility", title=entry["title"], place_id=None,
                        starts_at=_stamp(entry["starts_at"]), ends_at=_stamp(entry["ends_at"]),
                        replaces_item_id=old.item_id if old is not None else None, detail=entry["detail"]))
    return [replace(item, seq=seq) for seq, item in enumerate(out, 1)], picked


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
                    "AND trip_id=%s AND status='confirmed' "
                    # `[2026-10-14]` 수정 접수(`reopen`)도 「완료」하면 같은 여행에 묶인다 — 가장 나중에 확정한 판을 읽는다
                    "ORDER BY updated_at DESC LIMIT 1", (tenant_id, customer_id, trip_id))
        linked = cur.fetchone()
    return review.load(conn, tenant_id, linked[0], linked[1]) if linked else None
