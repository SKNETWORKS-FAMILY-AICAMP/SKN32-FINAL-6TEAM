"""숙소 이동을 지정하지 않은 호텔·조식을 여행의 같은 숙소에 연결한다."""
from __future__ import annotations

from typing import Any

from .line_parts import lookup_title, parse
from .places import distance_m, normalize_full


def is_stay(item: dict[str, Any]) -> bool:
    place = item.get("place") or {}
    categories = {s.strip() for s in str(place.get("category") or "").split(">")}
    return (item.get("kind") == "lodging" or (item.get("parts") or {}).get("content_type") == "32"
            or str(place.get("content_type_id") or "") == "32"
            or bool(categories & {"숙박", "숙소", "숙소 안 식사"}))


def generic(item: dict[str, Any]) -> bool:
    if (item.get("parts") or item.get("_lodging_parts") or {}).get("content_type") == "32":
        return True
    parts = parse(lookup_title(item.get("title")), kind_hint=item.get("kind"))
    return parts.nameless and parts.content_type == "32"


def same_place(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if not a or not b or any(p.get(k) is None for p in (a, b) for k in ("latitude", "longitude")):
        return False
    return (normalize_full(a.get("name") or "") == normalize_full(b.get("name") or "")
            and abs(float(a["latitude"]) - float(b["latitude"])) < 1e-6
            and abs(float(a["longitude"]) - float(b["longitude"])) < 1e-6)


def protected(item: dict[str, Any]) -> bool:
    return bool(item.get("locked") or item.get("booked") or item.get("vendor_booking"))


def groups(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """명시한 숙박 구간은 유지한다. 이름 없는 반복 줄만 공통 숙소로 묶는다."""
    stays = [x for x in items if is_stay(x) and not generic(x)]
    periods = [x for x in items if x.get("kind") == "lodging"]
    seeds = periods or stays
    out = {x["id"]: [x] for x in seeds}
    areas = {((x.get("parts") or x.get("_lodging_parts") or {}).get("area") or {}).get("name") for x in items if generic(x)} - {None}
    for item in items:
        if not generic(item) or item["id"] in out:
            continue
        active = [s for s in periods if s.get("date") and s.get("end_date") and item.get("date")
                  and (s["date"], s.get("starts_at") or "00:00") <= (item["date"], item.get("starts_at") or "00:00")
                  <= (s["end_date"], s.get("ends_at") or "23:59")]
        if len(active) == 1:
            key = active[0]["id"]
        elif len(seeds) == 1:
            key = seeds[0]["id"]
        elif seeds:
            # 여러 명시 숙소 중 어느 곳인지 판정할 수 없는 조식은 따로 둔다.
            key = item["id"]
        else:
            area = (item.get("parts") or item.get("_lodging_parts") or {}).get("area") or {}
            key = "trip:" + str(area.get("name") or "default") if len(areas) > 1 else "trip:default"
        out.setdefault(key, []).append(item)
    return [sorted(members, key=lambda x: (x.get("date") or "", x.get("starts_at") or "", x["id"]))
            for members in out.values()]


def group_for(items: list[dict[str, Any]], item: dict[str, Any]) -> list[dict[str, Any]]:
    return next((g for g in groups(items) if any(x["id"] == item["id"] for x in g)), [])


def anchor(members: list[dict[str, Any]], *, fixed_only: bool = False) -> tuple[dict[str, Any] | None, bool]:
    fixed = [x["place"] for x in members if x.get("place") and (protected(x) or not generic(x))]
    placed = fixed or ([] if fixed_only else [x["place"] for x in members if x.get("place")])
    if placed and all(same_place(placed[0], p) for p in placed):
        return placed[0], False
    return None, bool(fixed)


def visits(items: list[dict[str, Any]], members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    periods = [x for x in members if x.get("kind") == "lodging" and x.get("end_date")]
    return [x["place"] for x in items if not is_stay(x) and x.get("place")
            and all(x["place"].get(k) is not None for k in ("latitude", "longitude"))
            and (not periods or any(s["date"] <= (x.get("date") or "") <= s["end_date"] for s in periods))]


def center(items: list[dict[str, Any]], members: list[dict[str, Any]]) -> tuple[float, float] | None:
    area = next(((x.get("parts") or x.get("_lodging_parts") or {}).get("area") for x in members
                 if (x.get("parts") or x.get("_lodging_parts") or {}).get("area")), None)
    if area:
        return float(area["latitude"]), float(area["longitude"])
    points = visits(items, members)
    if not points:
        place, _ = anchor(members)
        points = [place] if place else []
    return ((sum(float(p["latitude"]) for p in points) / len(points),
             sum(float(p["longitude"]) for p in points) / len(points)) if points else None)


def score(place: dict[str, Any], points: list[dict[str, Any]]) -> float:
    return (sum(distance_m(float(place["latitude"]), float(place["longitude"]), float(p["latitude"]), float(p["longitude"]))
                for p in points) / len(points)) if points else 0.0


def as_place(place: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    meal = item.get("kind") == "dining"
    return {**place, "kind": "dining" if meal else "activity", "content_type_id": "32",
            "category": "숙소 안 식사" if meal else "숙박", "basis": "lodging_meal" if meal else "lodging"}


def annotate(items: list[dict[str, Any]]) -> None:
    for members in groups(items):
        place, conflict = anchor(members)
        known = [x["place"] for x in members if x.get("place")]
        mismatch = conflict or (bool(known) and any(not same_place(known[0], p) for p in known))
        data = {"id": members[0]["id"], "members": [x["id"] for x in members],
                "place": {k: place.get(k) for k in ("name", "latitude", "longitude")} if place and not mismatch else None}
        for item in members:
            item["lodging_group"] = data
            if mismatch:
                item["status"], item["can_lock"] = "review", False
                note = "같은 여행의 숙소가 서로 달라요 · 공통 숙소를 골라 주세요"
                if not any(r.get("text") == note for r in item.get("rows", [])):
                    item.setdefault("rows", []).append({"row": "place", "result": "warn", "text": note})


def prepare(payload: dict[str, Any]) -> dict[str, Any]:
    annotate(payload.get("items", []))
    needs_items = sum(x.get("status") == "review" for x in payload.get("items", []))
    needs_moves = sum(x.get("status") == "review" for x in payload.get("moves", []))
    payload["needs"] = {"items": needs_items, "moves": needs_moves, "total": needs_items + needs_moves}
    if needs_items + needs_moves:
        payload["ready"] = False
    return payload
