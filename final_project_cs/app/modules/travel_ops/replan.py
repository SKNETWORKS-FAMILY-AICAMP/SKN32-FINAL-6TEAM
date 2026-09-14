# -*- coding: utf-8 -*-
"""깨진 일정 항목의 대안 — 후보 만들기 · 고르기 · 알림 문구 (v11 §6-C).

★★**고르는 규칙(§6-C-2)** — 탈락 먼저, 그다음 사전식 비교. 벌점으로 섞지 않는다.

    탈락   재검증 불통과 · 그 시각 영업 안 함 · 가격·소요 모름 · 다음 일정 늦음 · 조건 위반
    비교   ① 바뀌는 항목 수  ② 추가 비용  ③ 원래 시각과의 차이  ④ 되돌리기 쉬운가
    동률   정규화한 후보 식별자 — 같은 입력에 같은 결과가 나오게 한다

★**하나를 고른다**(결정 15). 나머지 통과 후보는 **재요청용으로 둘까지** 들고 있는다
  (§6-C-4 6단계). 시나리오의 「대안 둘」은 여기서 나온다 — 나열해서 고객에게 고르게
  하지 않고, 최선을 적용한 뒤 「다른 안」으로 보인다.

★**첫 통과 후보에서 멈추지 않는다.** 첫 번째는 되는 안이지 최선이 아니다.

★우리가 고른 값(측정 아님) — 코드 상수로 모아 둔다:
    WALK_M_PER_MIN        80   도보 분당 거리
    ORDER_MARGIN_MIN      20   라스트오더 전에 확보해야 할 주문 여유
    SEATING_BUFFER_MIN    10   도착해 자리 잡는 데 드는 시간
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from typing import Any, Callable

WALK_M_PER_MIN = 80
ORDER_MARGIN_MIN = 20
SEATING_BUFFER_MIN = 10


@dataclass
class Candidate:
    key: str                           # 정규화한 후보 식별자 — 동률 처리용
    place: dict[str, Any] | None
    changed_items: int
    extra_cost_krw: int | None
    shift_minutes: int
    reversible_internally: bool = True
    rejected: list[str] = field(default_factory=list)
    recheck: dict[str, Any] | None = None
    option: dict[str, Any] | None = None     # 경로 후보일 때
    walk_min: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    def rank(self) -> tuple:
        return (self.changed_items, self.extra_cost_krw or 0, self.shift_minutes,
                0 if self.reversible_internally else 1, self.key)

    @property
    def name(self) -> str:
        if self.place:
            return self.place["name"]
        return (self.option or {}).get("label", self.key)


def distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a["latitude"], a["longitude"],
                                                b["latitude"], b["longitude"]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def walk_minutes(meters: float) -> int:
    return max(1, math.ceil(meters / WALK_M_PER_MIN))


def _hm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def _on(moment: datetime, hhmm: str) -> datetime:
    if hhmm in ("24:00",):
        return moment.replace(hour=23, minute=59, second=59, microsecond=0)
    hour, minute = map(int, hhmm.split(":"))
    return moment.replace(hour=hour, minute=minute, second=0, microsecond=0)


def open_during(place: dict[str, Any], start: datetime, end: datetime | None) -> bool | None:
    """영업시간 안인가. ★영업시간을 모르면 `None` — 「연다」로 읽지 않는다."""
    hours = (place.get("attributes") or {}).get("hours")
    if not hours or len(hours) != 2:
        return None
    return _on(start, hours[0]) <= start and (end or start) <= _on(start, hours[1])


def dining_fits(place: dict[str, Any], arrival: datetime, minutes: int) -> tuple[bool | None, str]:
    """그 시각에 들어가 `minutes` 동안 먹을 수 있나. (판정, 이유)."""
    end = arrival + timedelta(minutes=minutes)
    opened = open_during(place, arrival, end)
    if opened is None:
        return None, "영업시간을 확인할 수 없다"
    if not opened:
        return False, "그 시각 영업하지 않는다"
    attributes = place.get("attributes") or {}
    rest = attributes.get("break")
    if rest:
        rest_start, rest_end = _on(arrival, rest[0]), _on(arrival, rest[1])
        margin = attributes.get("last_order_before_break_min")
        last_order = rest_start - timedelta(minutes=margin or 0)
        if arrival < rest_end and arrival + timedelta(minutes=ORDER_MARGIN_MIN) > last_order:
            left = max(0, int((last_order - arrival).total_seconds() // 60))
            return False, (f"{rest[0]} 브레이크타임 전 라스트오더({_hm(last_order)})까지 "
                           f"{left}분 — 주문 가능한 시간이 촉박하다")
        if arrival < rest_start < end:
            return False, f"{rest[0]} 브레이크타임에 걸린다"
    return True, ""


#: 이 사건 종류는 **실내로 옮기면 원인이 사라진다** — 대안을 실내에서 찾는다.
WEATHER_LIKE = frozenset({"air_quality", "weather_warning", "forecast"})


# ── 후보: 활동 ─────────────────────────────────────────────────
def activity_candidates(*, original: dict[str, Any], places: list[dict[str, Any]],
                        start: datetime, end: datetime | None, causes: list[dict[str, Any]],
                        radius_m: int = 600) -> list[Candidate]:
    """깨진 활동의 대안 후보. ★원인이 날씨·대기질이면 **실내**에서만 찾는다."""
    indoor_only = any(cause.get("category") in WEATHER_LIKE for cause in causes)
    base_price = (original.get("attributes") or {}).get("price_krw")
    out = []
    for place in places:
        if place["place_id"] == original["place_id"] or place.get("kind") != "activity":
            continue
        if place.get("latitude") is None or distance_m(original, place) > radius_m:
            continue
        attributes = place.get("attributes") or {}
        if indoor_only and not attributes.get("indoor"):
            continue
        candidate = Candidate(key=str(place["place_id"]), place=place, changed_items=1,
                              extra_cost_krw=None, shift_minutes=0)
        price = attributes.get("price_krw")
        if price is None or base_price is None:
            candidate.rejected.append("가격을 몰라 추가 비용을 계산할 수 없다")
        else:
            candidate.extra_cost_krw = max(0, int(price) - int(base_price))
        opened = open_during(place, start, end)
        if opened is not True:
            candidate.rejected.append("그 시각 영업을 확인할 수 없다" if opened is None
                                      else "그 시각 영업하지 않는다")
        out.append(candidate)
    return out


# ── 후보: 식당 ─────────────────────────────────────────────────
def dining_candidates(*, original: dict[str, Any], places: list[dict[str, Any]],
                      arrival: datetime, minutes: int, constraints: dict[str, Any],
                      radius_m: int, next_start: datetime | None,
                      exclude: set[str] = frozenset()) -> list[Candidate]:
    """주변 식당 후보. ★조건(결제수단)은 **탈락**이지 감점이 아니다(§6-C-2)."""
    base_price = (original.get("attributes") or {}).get("price_krw")
    need_payment = constraints.get("payment")
    out = []
    for place in places:
        if place["place_id"] == original["place_id"] or place["place_id"] in exclude:
            continue
        if place.get("kind") != "dining" or place.get("latitude") is None:
            continue
        meters = distance_m(original, place)
        if meters > radius_m:
            continue
        walk = walk_minutes(meters)
        attributes = place.get("attributes") or {}
        candidate = Candidate(key=str(place["place_id"]), place=place, changed_items=1,
                              extra_cost_krw=None, shift_minutes=0, walk_min=walk)
        price = attributes.get("price_krw")
        if price is None or base_price is None:
            candidate.rejected.append("가격을 몰라 추가 비용을 계산할 수 없다")
        else:
            candidate.extra_cost_krw = max(0, int(price) - int(base_price))
        if need_payment and need_payment not in (attributes.get("payment") or []):
            candidate.rejected.append(f"결제 조건({need_payment}) 불충족")
        fits, why = dining_fits(place, arrival, minutes)
        if fits is not True:
            candidate.rejected.append(why)
        candidate.starts_at = arrival
        candidate.ends_at = arrival + timedelta(minutes=minutes)
        if next_start is not None and candidate.ends_at > next_start:
            candidate.rejected.append(f"다음 일정({_hm(next_start)})과 겹친다")
        out.append(candidate)
    return out


# ── 후보: 경로 ─────────────────────────────────────────────────
def route_candidates(*, route: dict[str, Any], depart: datetime, planned_arrival: datetime,
                     next_start: datetime | None,
                     events: dict[str, dict[str, Any]]) -> list[Candidate]:
    """구간의 경로 후보. ★사건이 걸린 경로는 **효과대로** 다룬다.

        무정차(skip_station)   그 역을 쓰는 경로는 도달 불가 — 탈락
        도로 통제(road_control) 소요가 `eta_min_if_controlled` 로 바뀐다.
                                값이 없으면(택시 등) **소요 산출 불가 — 탈락**
    """
    options = {option["id"]: option for option in route.get("options", [])}
    planned_fare = (options.get(route.get("planned")) or {}).get("fare_krw") or 0
    out = []
    for option in options.values():
        eta = option.get("eta_min")
        candidate = Candidate(key=option["id"], place=None, changed_items=1,
                              extra_cost_krw=None, shift_minutes=0, option=dict(option))
        for target in option.get("uses", []):
            event = events.get(target)
            if event is None:
                continue
            if event.get("effect") == "skip_station":
                candidate.rejected.append(f"{event.get('summary')} — 이 경로로는 도달할 수 없다")
            elif event.get("effect") == "road_control":
                eta = option.get("eta_min_if_controlled")
                if eta is None:
                    candidate.rejected.append("통제 구간의 실제 소요를 확인할 수 없다")
        if eta is None:
            if not candidate.rejected:
                candidate.rejected.append("소요를 확인할 수 없다")
        else:
            arrival = depart + timedelta(minutes=int(eta))
            candidate.option["eta_effective"] = int(eta)
            candidate.starts_at, candidate.ends_at = depart, arrival
            candidate.shift_minutes = max(0, int((arrival - planned_arrival).total_seconds() // 60))
            if next_start is not None and arrival > next_start:
                candidate.rejected.append(f"다음 일정({_hm(next_start)})에 늦는다 — 도착 {_hm(arrival)}")
        fare = option.get("fare_krw")
        candidate.extra_cost_krw = None if fare is None else max(0, int(fare) - int(planned_fare))
        if fare is None and not candidate.rejected:
            candidate.rejected.append("요금을 몰라 추가 비용을 계산할 수 없다")
        out.append(candidate)
    return out


# ── 후보: 매장(재고) ───────────────────────────────────────────
def _point_segment_detour(a: dict[str, Any], b: dict[str, Any], c: dict[str, Any]) -> float:
    """a→c→b 로 돌아갈 때 늘어나는 거리."""
    return distance_m(a, c) + distance_m(c, b) - distance_m(a, b)


def store_candidates(*, here: dict[str, Any], home: dict[str, Any], places: list[dict[str, Any]],
                     products: list[str], at: datetime, max_detour_m: int = 1500) -> list[Candidate]:
    """같은 상품을 **취급할 만한** 매장. ★재고는 확인하지 않는다 — 소스가 없다."""
    wanted = {"명절 선물세트"} if any("선물세트" in p for p in products) else set(products)
    out = []
    for place in places:
        if place["place_id"] == here["place_id"] or place.get("latitude") is None:
            continue
        attributes = place.get("attributes") or {}
        if not wanted & set(attributes.get("sells") or []):
            continue
        detour = _point_segment_detour(here, home, place)
        candidate = Candidate(key=str(place["place_id"]), place=place, changed_items=0,
                              extra_cost_krw=0, shift_minutes=int(detour // WALK_M_PER_MIN))
        candidate.option = {"detour_m": round(detour)}
        if detour > max_detour_m:
            candidate.rejected.append(f"귀가 동선에서 {round(detour)}m 벗어난다")
        if open_during(place, at, at) is not True:
            candidate.rejected.append("지금 영업을 확인할 수 없다")
        out.append(candidate)
    return out


def choose(candidates: list[Candidate],
           recheck: Callable[[Candidate], dict[str, Any]] | None = None) -> tuple[
               Candidate | None, list[Candidate], list[Candidate]]:
    """(최선, 재요청용 둘, 탈락). ★재검증은 **탈락을 통과한 것에만** 돌린다."""
    survivors, rejected = [], []
    for candidate in candidates:
        if not candidate.rejected and recheck is not None:
            report = recheck(candidate)
            candidate.recheck = report
            if report.get("verdict") != "clear":
                candidate.rejected.append(f"재검증 불통과: {report.get('verdict')}")
        (rejected if candidate.rejected else survivors).append(candidate)
    survivors.sort(key=Candidate.rank)
    if not survivors:
        return None, [], rejected
    return survivors[0], survivors[1:3], rejected


# ── 알림 문구 ──────────────────────────────────────────────────
def _part_of_day(moment: datetime) -> str:
    return "오전" if moment.hour < 12 else "오후"


def _reason_phrase(causes: list[dict[str, Any]], place: dict[str, Any]) -> str:
    """★원인에서만 문장을 만든다. 원인에 없는 이유를 붙이지 않는다."""
    categories = {cause.get("category") for cause in causes}
    attributes = place.get("attributes") or {}
    if "air_quality" in categories and attributes.get("view_dependent"):
        return "시야 확보가 어려울 것으로 예상되어"
    if "air_quality" in categories:
        return "미세먼지 기준을 넘어 야외 활동이 어려울 것으로 예상되어"
    if categories & {"weather_warning", "forecast"}:
        return "기상 악화가 예상되어"
    return "운영 상황이 바뀌어"


def alternate_record(candidate: Candidate) -> dict[str, Any]:
    """재요청용으로 들고 있는 「다른 안」 하나(§6-C-4 6단계).

    ★이름만 두면 재요청 때 **다시 계산**해야 하고, 그 사이 입력이 바뀌면 고객이 본
      「다른 안」과 다른 것이 들어간다. 적용에 필요한 값을 그대로 적어 둔다.
    """
    return {"key": candidate.key, "name": candidate.name,
            "place_id": candidate.place["place_id"] if candidate.place else None,
            "option": (candidate.option or {}).get("id") if candidate.option else None,
            "option_label": (candidate.option or {}).get("label") if candidate.option else None,
            "starts_at": candidate.starts_at.isoformat() if candidate.starts_at else None,
            "ends_at": candidate.ends_at.isoformat() if candidate.ends_at else None,
            "walk_min": candidate.walk_min}


def _notice(text: str, *, causes, changed, alternates, replay, **extra) -> dict[str, Any]:
    return {"text": text, "language": "ko",      # ★고객 언어 옮김은 보낼 때(결정 14)
            "causes": causes, "changed": changed,
            "other_options": [c.name for c in alternates], "replay": replay, **extra}


def change_notice(*, original: dict[str, Any], replacement: dict[str, Any], start: datetime,
                  causes: list[dict[str, Any]], alternates: list[Candidate],
                  replay: bool) -> dict[str, Any]:
    """활동 변경 통지."""
    same_building = (original.get("attributes") or {}).get("building") and \
        (original.get("attributes") or {}).get("building") == \
        (replacement.get("attributes") or {}).get("building")
    area = (original.get("attributes") or {}).get("area")
    subject = f"{original['name']} {area}" if area else original["name"]
    floor = (replacement.get("attributes") or {}).get("floor")
    where = " ".join(part for part in (
        "같은 건물" if same_building else None, floor, replacement["name"]) if part)
    text = (f"오늘 {_part_of_day(start)} {subject}는 {_reason_phrase(causes, original)}, "
            f"{where}으로 변경됩니다.")
    return _notice(text, causes=causes, alternates=alternates, replay=replay,
                   changed={"from": original["name"], "to": replacement["name"],
                            "at": start.isoformat()})


def route_notice(*, route: dict[str, Any], planned: dict[str, Any], best: Candidate,
                 alternates: list[Candidate], rejected: list[Candidate],
                 causes: list[dict[str, Any]], planned_arrival: datetime,
                 next_title: str | None, replay: bool) -> dict[str, Any]:
    """경로 변경 통지. ★탈락시킨 수단도 **왜 뺐는지** 말한다(택시 「확인 불가」)."""
    option = best.option or {}
    lines = [f"{cause.get('summary')}." for cause in causes if cause.get("summary")]
    if best.key != route.get("planned"):
        lines.append(f"{option.get('label')}로 바꿔 안내합니다"
                     f"(도보 {option.get('walk_m')}m, 예상 {option.get('eta_effective')}분).")
    if alternates:
        lines.append("다른 안: " + ", ".join(
            f"{(c.option or {}).get('label')}(도보 {(c.option or {}).get('walk_m')}m, "
            f"예상 {(c.option or {}).get('eta_effective')}분)" for c in alternates) + ".")
    for candidate in rejected:
        if candidate.key == route.get("planned"):
            continue
        if any("실제 소요" in reason for reason in candidate.rejected):
            lines.append(f"{(candidate.option or {}).get('label')}는 통제 구간의 실제 소요를 "
                         f"확인할 수 없어 권하지 않습니다.")
    if option.get("walk_note"):
        lines.append(f"{option['walk_note']}합니다.")
    if best.ends_at and best.ends_at > planned_arrival and next_title:
        lines.append(f"도착이 조금 늦어지지만 {next_title} 일정에는 영향이 없습니다.")
    return _notice(" ".join(lines), causes=causes, alternates=alternates, replay=replay,
                   changed={"from": planned.get("label"), "to": option.get("label")},
                   excluded={(c.option or {}).get("label"): c.rejected for c in rejected})


def dining_notice(*, original: dict[str, Any], best: Candidate, alternates: list[Candidate],
                  reason: str, cause: dict[str, Any], after: str | None,
                  constraint_note: str | None = None) -> dict[str, Any]:
    """식사 변경 통지."""
    parts = [f"{reason}.",
             f"도보 {best.walk_min}분 거리{', ' + constraint_note if constraint_note else ''}"
             f" {best.name}(으)로 안내합니다({_hm(best.starts_at)} 입장)."]
    if alternates:
        parts.append("다른 안: " + ", ".join(f"{c.name}(도보 {c.walk_min}분)"
                                            for c in alternates) + ".")
    if after:
        parts.append(f"이후 {after} 일정에는 영향이 없습니다.")
    return _notice(" ".join(parts), causes=[cause], alternates=alternates, replay=False,
                   changed={"from": original["name"], "to": best.name,
                            "at": best.starts_at.isoformat()})


__all__ = ["Candidate", "activity_candidates", "alternate_record", "change_notice", "choose", "dining_candidates",
           "dining_fits", "dining_notice", "distance_m", "open_during", "route_candidates",
           "route_notice", "store_candidates", "walk_minutes"]
