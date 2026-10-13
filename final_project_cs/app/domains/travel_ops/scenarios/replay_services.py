"""시나리오에 기록된 구간만 재생한다. 실제 이동 정확도의 검증 근거가 아니다."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from app.domains.travel_ops.components.planning.replan import distance_m


def replay_leg_services(data):
    """대본의 앞뒤 장소·경로를 고정해 재생한다. 운영 조립에서는 부르지 않는다.

    장소 교체는 대본 장소 주변 1.2km까지만 같은 합성 구간으로 본다.
    범위를 벗어나면 새 소요를 만들지 않고 scenario_route_not_recorded를 반환한다.
    """
    seed = deepcopy(data)
    places = {p["key"]: p for p in seed["places"]}
    ordered = sorted(seed["items"], key=lambda item: item["seq"])
    records = []
    for index, item in enumerate(ordered):
        if item.get("route") not in seed["routes"]:
            continue
        before = next((p for p in reversed(ordered[:index]) if p.get("place") in places), None)
        after = next((p for p in ordered[index + 1:] if p.get("place") in places), None)
        if before and after:
            records.append((places[before["place"]], places[after["place"]], seed["routes"][item["route"]]))

    def meters(a, b):
        return distance_m({"latitude": a["lat"], "longitude": a["lon"]},
                          {"latitude": b["lat"], "longitude": b["lon"]})

    def planner(party_size, constraints, **kwargs):
        def leg(a, b, arrive, not_before=None):
            matched = [(meters(a, start) + meters(b, end), route)
                       for start, end, route in records
                       if meters(a, start) <= 1200 and meters(b, end) <= 1200]
            if not matched:
                return None, {"code": "scenario_route_not_recorded", "source": "scenario_replay"}
            route = deepcopy(min(matched, key=lambda pair: pair[0])[1])
            option = next(o for o in route["options"] if o["id"] == route["planned"])
            minutes = int(option["eta_min"])
            duration = timedelta(minutes=minutes)
            start = arrive - duration if not_before is None else not_before
            if start + duration > arrive:
                return None, {"code": "arrive_late", "source": "scenario_replay"}
            route.update({"from": a["name"], "to": b["name"], "source": "scenario_replay"})
            return {"route": route, "starts_at": start, "ends_at": start + duration,
                    "eta_min": minutes, "left_out": []}, None
        return leg

    return {("legs", "leg_planner"): planner,
            ("legs", "walk_limit_m"): lambda: 1200,
            ("legs", "basis"): lambda: {"mode": "scenario_replay"}}
