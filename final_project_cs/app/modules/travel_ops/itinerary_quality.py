# -*- coding: utf-8 -*-
"""일정 **품질 경고** — 거절하지 않고 알린다. 체크리스트 v2의 T7(끼니) · T8(같은 곳 두 번) · T9(왔다 갔다) · T13(하루 마감) · O4(식당 라스트오더). `[2026-10-03]`

☆왜: 사람이 일정표를 믿기 전에 하는 확인 중 **받을 때 코드로 보지 않는** 것이 있었다(`program/research/여행자_확인_체크리스트_v2_2026-10-03.md`).
생성기는 같은 곳 · 끼니를 구성으로 지키지만, 외부 에이전트가 만든 일정(등록 길)은 같은 곳을 두 번 넣어도, 하루 종일 한 끼도 없어도, 지도 위를 왔다 갔다 해도 아무도 말하지 않았다.
외부 연구(AI 가 짠 일정 356건)는 이런 날이 흔하다고 한다 — 같은 곳 두 번 5.1% · 지그재그 9.5%의 날.

★`check_itinerary` 의 **위반**과 다르다. 위반은 「그대로는 못 한다」(겹침 · 닫힌 곳)라 등록을 거절하고, 이것은 「이상해 보인다」라 알리기만 한다 —
같은 곳을 두 번 가는 일정도, 점심을 거르는 일정도, 시간이 정해져 동선이 어쩔 수 없는 일정도 **가능은 하다**. 거절하면 맞는 일정이 막힌다.
그래서 화면 「살펴볼 점」(`warnings` — 밀도 경고와 같은 목록 · 같은 모양)으로 보내고, 고치는 것은 고객·에이전트에게 맡긴다.

★**일정에 있는 값만으로 센다**(바깥 조회 없음). 모르는 것은 세지 않는다 — 좌표가 없는 장소는 왔다 갔다를 못 재고(그 장소를 빼고 센다),
식사 항목 이름은 보지 않는다(`kind == "dining"` 만 식사다 — 외부가 다른 종류 이름을 쓰면 끼니가 없다고 오경고할 수 있다는 한계는 문서에 적었다).

★판정 입력은 `Part`(`itinerary_checks`)이다. 같은 곳 판정은 생성기가 쓰는 `itinerary_changes.same_site` 를 그대로 써서 두 길의 기준이 갈리지 않는다.
임계값은 `config/guardrails.yaml` 의 `travel.quality` 한 곳에 있다.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from itertools import permutations
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from app.core.settings import get_guardrails

from .itinerary_checks import Part

KST = ZoneInfo("Asia/Seoul")
#: 식사로 세는 항목 종류 — 생성기·밀도 계산이 쓰는 이름 그대로
MEAL_KIND = "dining"
ACTIVITY_KIND = "activity"
#: 식사 항목에 길이가 없을 때 두는 시간(분) — 생성기의 한 끼(`planner.MEAL_MIN`)와 같다
_MEAL_FALLBACK_MIN = 60
_MEAL_LABEL = {"lunch": "점심", "dinner": "저녁"}


def quality_warnings(parts: Iterable[Part]) -> list[dict[str, Any]]:
    """그날그날 본 품질 경고들. 모양은 밀도 경고와 같다(`code` · `date` · `reason` · `remedy`) + 가리키는 항목 순번 `items`.

    이동 항목은 하루의 모양에서 뺀다(장소가 아니라 장소 사이다). 날짜는 서울 시각 기준이다.
    """
    policy = dict(get_guardrails().get("travel.quality"))
    by_day: dict[date, list[Part]] = {}
    for part in sorted(parts, key=lambda p: (p.starts_at, p.seq)):
        if part.kind == "mobility":
            continue
        by_day.setdefault(part.starts_at.astimezone(KST).date(), []).append(part)
    found: list[dict[str, Any]] = []
    for day, day_parts in sorted(by_day.items()):
        found += _same_place(day, day_parts)
        found += _meals(day, day_parts, policy)
        found += _zigzag(day, day_parts, dict(policy["zigzag"]))
        found += _day_end(day, day_parts)
        found += _last_order(day, day_parts)
    return found


def _warning(code: str, day: date, reason: str, remedy: str, seqs: Iterable[int], **extra: Any) -> dict[str, Any]:
    return {"code": code, "date": str(day), "reason": reason, "remedy": remedy, "items": list(seqs), **extra}


def _clock(value: Any) -> time:
    hour, minute = str(value).split(":")
    return time(int(hour), int(minute))


# ── T8 같은 곳 두 번 ───────────────────────────────────────────
def _same_place(day: date, parts: list[Part]) -> list[dict[str, Any]]:
    """그날 같은 곳이 두 번 들어 있는가. 활동은 생성기와 같은 규칙(`same_site` — 같은 주소 · 30m · 이름 첫 낱말), 식당은 같은 가게(같은 장소 id · 원장 id · 이름)만 —
    식당은 같은 건물에 다른 가게가 흔해 거리로 가르지 않는다. 한 쌍을 한 번만 말한다(앞서 말한 곳과 또 겹치는 셋째는 따로 말한다)."""
    found: list[dict[str, Any]] = []
    seen: list[Part] = []
    for part in parts:
        if part.kind not in (ACTIVITY_KIND, MEAL_KIND) or not part.place:
            continue
        twin = next((earlier for earlier in seen if earlier.kind == part.kind and _same(earlier, part)), None)
        if twin is not None:
            found.append(_warning(
                "same_place_twice", day,
                f"{twin.title} 와 {part.title} 은(는) 같은 곳이다 — 그날 두 번 들어 있다",
                "한 번으로 줄이거나 둘 중 하나를 다른 곳으로 바꾼다(일부러 다시 가는 것이면 그대로 둔다)", (twin.seq, part.seq)))
        seen.append(part)
    return found


def _same(a: Part, b: Part) -> bool:
    place_a, place_b = dict(a.place or {}), dict(b.place or {})
    ids = (place_a.get("place_id"), place_b.get("place_id"))
    if ids[0] and ids[0] == ids[1]:
        return True
    if a.kind == MEAL_KIND:
        uid_a = (place_a.get("attributes") or {}).get("dining_place_uid")
        uid_b = (place_b.get("attributes") or {}).get("dining_place_uid")
        if uid_a and uid_a == uid_b:
            return True
        name_a, name_b = str(place_a.get("name") or "").strip(), str(place_b.get("name") or "").strip()
        return bool(name_a) and name_a == name_b
    from .itinerary_changes import same_site

    return same_site(place_a, place_b)


# ── T7 끼니 ─────────────────────────────────────────────────
def _meals(day: date, parts: list[Part], policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """하루가 점심·저녁 창을 **통째로 덮는데** 그 창과 겹치는 식사가 없으면 알린다. 하루가 창을 덮지 않으면(늦게 도착 · 일찍 끝남) 안 본다."""
    if len(parts) < int(policy["meal_min_items"]):
        return []
    day_start = parts[0].starts_at
    day_end = max(p.ends_at or p.starts_at for p in parts)
    meals = [p for p in parts if p.kind == MEAL_KIND]
    found: list[dict[str, Any]] = []
    for name, (opens, closes) in dict(policy["meal_windows"]).items():
        window_start = datetime.combine(day, _clock(opens), tzinfo=KST)
        window_end = datetime.combine(day, _clock(closes), tzinfo=KST)
        if day_start > window_start or day_end < window_end:
            continue
        if any(m.starts_at <= window_end and (m.ends_at or m.starts_at + timedelta(minutes=_MEAL_FALLBACK_MIN)) >= window_start
               for m in meals):
            continue
        label = _MEAL_LABEL.get(name, name)
        found.append(_warning(
            "meal_missing", day,
            f"{label} 시간대({opens}~{closes})에 식사가 없다 — 그날 일정이 그 시간을 통째로 덮는다",
            "그 시간대에 식사 항목을 넣는다(일부러 거르는 일정이면 그대로 둔다)",
            [p.seq for p in parts if p.starts_at <= window_end and (p.ends_at or p.starts_at) >= window_start]))
    return found


# ── T9 왔다 갔다 ────────────────────────────────────────────
def _fixed(part: Part) -> bool:
    """시간이 정해져 순서를 못 바꾸는 일정 — 예약 · 고객이 고정."""
    detail = part.detail or {}
    return bool(detail.get("booking") or detail.get("reservation") or detail.get("customer_pinned"))


def _zigzag(day: date, parts: list[Part], policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """그날 활동 장소를 시간 순서대로 도는 길이가, 같은 곳들을 가장 짧게 도는 순서의 길이보다 훨씬 긴가. 좌표 있는 활동만 센다.

    ★순서를 **다 세어 본다**(`max_stops` 이하라 가능). 식사는 뺀다 — 끼니 시각이 순서를 정하는 일이 흔하다. 시간이 정해진 일정이 둘 이상이면 안 본다(순서를 못 바꾼다).
    가장 짧은 순서는 처음·끝이 자유인 열린 경로 — 숙소에서 출발하는 일정이면 실제 최단은 이보다 길 수 있어 **경고가 덜 나오는 쪽**(보수적)이다."""
    stops = [p for p in parts if p.kind == ACTIVITY_KIND and p.place
             and p.place.get("latitude") is not None and p.place.get("longitude") is not None]
    if not int(policy["min_stops"]) <= len(stops) <= int(policy["max_stops"]):
        return []
    if sum(1 for p in stops if _fixed(p)) > 1:
        return []
    from .replan import distance_m

    count = len(stops)
    dist = [[0.0 if i == j else distance_m(stops[i].place, stops[j].place) for j in range(count)] for i in range(count)]

    def length(order: tuple[int, ...]) -> float:
        return sum(dist[a][b] for a, b in zip(order, order[1:]))

    current = length(tuple(range(count)))
    best_order = min(permutations(range(count)), key=length)
    best = length(best_order)
    if current - best < float(policy["min_extra_m"]) or current < float(policy["ratio"]) * best:
        return []
    return [_warning(
        "route_zigzag", day,
        f"그날 활동 {count}곳을 도는 길이가 약 {current / 1000:.1f}km 인데, 순서를 바꾸면 약 {best / 1000:.1f}km 로 돌 수 있다",
        "시간이 정해진 예약이 아니면 가까운 곳끼리 묶어 순서를 바꾼다",
        [p.seq for p in stops], better_order=[stops[i].seq for i in best_order])]


# ── T13 하루 마감 ────────────────────────────────────────────
def _day_end(day: date, parts: list[Part]) -> list[dict[str, Any]]:
    """그날 마지막 일정이 **하루 마감**(생성기의 하루 창 끝 `travel.day_window.default_end`, 22:00) 뒤에 끝나는가. `[체크리스트 T13]`

    생성기는 마감을 넘기면 거절하지만(「상품의 약속」) 고객·외부 에이전트가 준 일정에는 거절하지 않고 알린다 — 일부러 늦게까지 가는 일정(야경 · 공연)도 가능은 하다.
    끝 시각이 없으면 시작 시각으로 본다. 늦게 끝나는 항목을 모두 이름으로 말한다."""
    limit_text = str(get_guardrails().get("travel.day_window.default_end"))
    limit = datetime.combine(day, _clock(limit_text), tzinfo=KST)
    late = [p for p in parts if (p.ends_at or p.starts_at).astimezone(KST) > limit]
    if not late:
        return []
    last = max(late, key=lambda p: (p.ends_at or p.starts_at))
    finishes = (last.ends_at or last.starts_at).astimezone(KST)
    names = ", ".join(p.title for p in late)
    return [_warning(
        "past_day_end", day,
        f"{names} — {finishes:%H:%M}에 끝나 하루 마감({limit_text})을 넘는다",
        "마감 안에 끝나게 앞당기거나 줄인다(일부러 늦게까지 가는 일정이면 그대로 둔다)", [p.seq for p in late])]


# ── O4 식당 라스트오더 ───────────────────────────────────────
def _last_order(day: date, parts: list[Part]) -> list[dict[str, Any]]:
    """식당에 도착해 **주문할 시간이 촉박**한가. `[체크리스트 O4]` 대체 식당을 고를 때 쓰던 규칙(`replan.dining_fits` · `dining_warnings`)을 받은 일정에도 같은 기준으로 건다 —
    라스트오더를 **알면** 도착 + 20분이 그 시각을 넘을 때(브레이크 앞 · 영업 종료 앞), **모르면** 식사가 영업 종료 · 브레이크 시작 1시간 안에 끝날 때 「마지막 주문을 확인해 주세요」.

    ★영업하지 않는 시각 · 브레이크에 걸치는 것은 위반(`check_itinerary`)이 이미 막는다 — 여기서는 **라스트오더 이유**만 센다(같은 말을 두 번 하지 않는다)."""
    from .replan import dining_fits, dining_warnings

    found: list[dict[str, Any]] = []
    for part in parts:
        if part.kind != MEAL_KIND or not part.place:
            continue
        arrival = part.starts_at.astimezone(KST)
        end = (part.ends_at or part.starts_at + timedelta(minutes=_MEAL_FALLBACK_MIN)).astimezone(KST)
        minutes = max(1, int((end - arrival).total_seconds() // 60))
        place = dict(part.place)
        ok, why = dining_fits(place, arrival, minutes)
        if ok is False and "라스트오더" in why:
            found.append(_warning(
                "last_order_tight", day, f"{part.title}: {why}",
                "더 일찍 도착하게 앞당기거나 마지막 주문 시각을 미리 확인한다", [part.seq]))
        for note in dining_warnings(place, arrival, minutes):
            found.append(_warning("last_order_unknown", day, f"{part.title}: {note}", "방문 전에 마지막 주문 시각을 확인한다", [part.seq]))
    return found


__all__ = ["quality_warnings"]
