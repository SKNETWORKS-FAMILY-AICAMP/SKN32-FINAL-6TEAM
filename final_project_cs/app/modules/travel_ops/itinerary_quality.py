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

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

from app.core.settings import get_guardrails

from .itinerary_checks import Part, check_itinerary, seoul_part

log = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
#: 식사로 세는 항목 종류 — 생성기·밀도 계산이 쓰는 이름 그대로
MEAL_KIND = "dining"
ACTIVITY_KIND = "activity"
#: 식사 항목에 길이가 없을 때 두는 시간(분) — 생성기의 한 끼(`planner.MEAL_MIN`)와 같다
_MEAL_FALLBACK_MIN = 60
_MEAL_LABEL = {"lunch": "점심", "dinner": "저녁"}


#: 하루의 모양을 만드는 항목 — 활동 · 식사만. 이동은 장소가 아니라 장소 사이고, 숙소 · 항공은 하루를 넘겨 이어져(체크인~다음 날 체크아웃 · 심야 항공) 「하루가 끝나는 시각」을 늘린다.
#: ☆`[2026-10-03 적대 검토]` 전에는 이동만 뺐다 — 숙소 항목이 하루 끝을 다음 날로 늘려 「저녁 창을 통째로 덮는다」 · 「마감을 넘는다」고 오경고했다.
_DAY_KINDS = (ACTIVITY_KIND, MEAL_KIND)
#: 점검 이름 → 고객에게 보일 말. 한 점검이 죽으면 이 말로 알린다
_RULE_LABEL = {"same_place": "같은 곳 두 번", "meals": "끼니", "zigzag": "동선", "day_end": "하루 마감", "last_order": "식당 마지막 주문"}


def quality_warnings(parts: Iterable[Part], constraints: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """그날그날 본 품질 경고들. 모양은 밀도 경고와 같다(`code` · `date` · `reason` · `remedy`) + 가리키는 항목 순번 `items`.

    활동 · 식사 항목만 하루의 모양에 센다(`_DAY_KINDS`). 날짜는 서울 시각 기준이다 — 시간대 없는 시각은 서울로 읽는다(`seoul_part`).
    `constraints` — 사용자가 하루 시간을 직접 준 여행(`density`)은 하루 마감을 밀도 계산이 이미 말하니 `past_day_end` 를 건너뛴다.

    ★`[2026-10-03 적대 검토]` **점검 하나가 죽어도 나머지는 나간다.** 이 계산은 여행 화면이 매 조회마다 부르는데, 규칙 하나가 장소 값 하나에 예외를 내면 그 여행은 영구히 500 이었다.
    죽은 점검은 **조용히 빼지 않고** 로그에 남기고 `quality_check_skipped` 경고로 세어 알린다(조용한 스킵 금지 — 빼면 「경고 없음」이 「점검을 못 함」처럼 보이지 않는다).
    """
    policy = dict(get_guardrails().get("travel.quality"))
    by_day: dict[date, list[Part]] = {}
    for part in sorted((seoul_part(p) for p in parts), key=lambda p: (p.starts_at, p.seq)):
        if part.kind not in _DAY_KINDS:
            continue
        by_day.setdefault(part.starts_at.date(), []).append(part)
    own_window = "density" in (constraints or {})
    found: list[dict[str, Any]] = []
    failed: dict[str, date] = {}

    def run(name: str, day: date, rule: Callable[[], list[dict[str, Any]]]) -> None:
        try:
            found.extend(rule())
        except Exception:                       # 어떤 입력이 왔든 화면을 죽이지 않는다 — 대신 로그 + 경고로 센다
            log.warning("일정 품질 점검 %s 실패 — %s 의 그날은 건너뛴다", name, day, exc_info=True)
            failed.setdefault(name, day)

    for day, day_parts in sorted(by_day.items()):
        run("same_place", day, lambda: _same_place(day, day_parts))
        run("meals", day, lambda: _meals(day, day_parts, policy))
        run("zigzag", day, lambda: _zigzag(day, day_parts, dict(policy["zigzag"])))
        if not own_window:
            run("day_end", day, lambda: _day_end(day, day_parts))
        run("last_order", day, lambda: _last_order(day, day_parts))
    if failed:
        names = ", ".join(_RULE_LABEL.get(name, name) for name in failed)
        found.append({"code": "quality_check_skipped", "date": str(min(failed.values())),
                      "reason": f"일부 점검({names})을 하지 못했어요 — 일정에 읽을 수 없는 값이 있을 수 있어요. 이 칸의 경고가 없다고 문제가 없다는 뜻은 아니에요",
                      "remedy": "장소 정보(영업시간 · 브레이크 시간)가 올바른지 확인하거나 다시 열어 보세요", "items": [], "rules": list(failed)})
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
    """하루가 점심·저녁 창을 **통째로 덮고** 그 창과 겹치는 식사도 없고 **식사할 틈도 없으면** 알린다. 하루가 창을 덮지 않으면(늦게 도착 · 일찍 끝남) 안 본다.

    ★`[2026-10-03 적대 검토]` 틈 조건을 더했다 — 점심을 일정표에 안 적고 자유 시간으로 두는 일정(궁 11:30 끝 · 박물관 13:30 시작 — 사이 2시간)이 흔한데,
    그 일정까지 「식사가 없다」고 하면 맞는 일정에 잡음이다. 창 안의 가장 긴 빈 틈이 `meal_min_gap_minutes`(60분) 이상이면 먹을 시간은 있다 — 내지 않는다."""
    if len(parts) < int(policy["meal_min_items"]):
        return []
    day_start = parts[0].starts_at
    day_end = max(p.ends_at or p.starts_at for p in parts)
    meals = [p for p in parts if p.kind == MEAL_KIND]
    need = timedelta(minutes=float(policy["meal_min_gap_minutes"]))
    found: list[dict[str, Any]] = []
    for name, (opens, closes) in dict(policy["meal_windows"]).items():
        window_start = datetime.combine(day, _clock(opens), tzinfo=KST)
        window_end = datetime.combine(day, _clock(closes), tzinfo=KST)
        if day_start > window_start or day_end < window_end:
            continue
        if any(m.starts_at <= window_end and (m.ends_at or m.starts_at + timedelta(minutes=_MEAL_FALLBACK_MIN)) >= window_start
               for m in meals):
            continue
        gap = _longest_gap(parts, window_start, window_end)
        if gap >= need:
            continue
        label = _MEAL_LABEL.get(name, name)
        found.append(_warning(
            "meal_missing", day,
            f"{label} 시간대({opens}~{closes})에 식사 일정이 없고 식사할 틈도 {int(gap.total_seconds() // 60)}분뿐이다 — 다른 일정이 그 시간을 채운다",
            "그 시간대에 식사 항목을 넣거나 일정 사이에 식사할 틈을 둔다(일부러 거르는 일정이면 그대로 둔다)",
            [p.seq for p in parts if p.starts_at <= window_end and (p.ends_at or p.starts_at) >= window_start]))
    return found


def _longest_gap(parts: list[Part], window_start: datetime, window_end: datetime) -> timedelta:
    """창 안에서 어떤 일정도 없는 **가장 긴 빈 틈**."""
    spans = sorted((max(p.starts_at, window_start), min(p.ends_at or p.starts_at, window_end)) for p in parts
                   if p.starts_at < window_end and (p.ends_at or p.starts_at) > window_start)
    cursor, best = window_start, timedelta(0)
    for start, end in spans:
        best = max(best, start - cursor)
        cursor = max(cursor, end)
    return max(best, window_end - cursor)


# ── T9 왔다 갔다 ────────────────────────────────────────────
def _fixed(part: Part) -> bool:
    """시간이 정해져 순서를 못 바꾸는 일정 — 예약 · 고객이 고정."""
    detail = part.detail or {}
    return bool(detail.get("booking") or detail.get("reservation") or detail.get("customer_pinned"))


def _zigzag(day: date, parts: list[Part], policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """그날 활동 장소를 시간 순서대로 도는 길이가, 같은 곳들을 가장 짧게 도는 순서의 길이보다 훨씬 긴가. 좌표 있는 활동만 센다.

    ★가장 짧은 순서를 **정확히** 구한다(`_shortest_open_path` — 방문 집합 위의 동적 계획법). `[2026-10-03 적대 검토]` 전에는 모든 순서를 세어 8곳이면 4만 가지 · 여행 화면을 열 때마다 그날마다 약 1.1초였다. 식사는 뺀다 — 끼니 시각이 순서를 정하는 일이 흔하다. 시간이 정해진 일정이 둘 이상이면 안 본다(순서를 못 바꾼다).
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
    current = sum(dist[a][b] for a, b in zip(range(count), range(1, count)))
    best_order = _shortest_open_path(dist)
    best = sum(dist[a][b] for a, b in zip(best_order, best_order[1:]))
    if current - best < float(policy["min_extra_m"]) or current < float(policy["ratio"]) * best:
        return []
    return [_warning(
        "route_zigzag", day,
        f"그날 활동 {count}곳을 도는 길이가 약 {current / 1000:.1f}km 인데, 순서를 바꾸면 약 {best / 1000:.1f}km 로 돌 수 있다",
        "시간이 정해진 예약이 아니면 가까운 곳끼리 묶어 순서를 바꾼다",
        [p.seq for p in stops], better_order=[stops[i].seq for i in best_order])]


def _shortest_open_path(dist: list[list[float]]) -> tuple[int, ...]:
    """모든 점을 한 번씩 지나는 **가장 짧은 열린 경로**(처음 · 끝이 자유)의 순서. 방문한 집합 위의 동적 계획법 — 점이 8개면 약 1.6만 번 계산이다(전수 순열은 4만 가지 × 길이 합).
    같은 길이면 앞서 찾은 것을 유지한다(`<` 로만 바꾼다)."""
    count = len(dist)
    full = (1 << count) - 1
    inf = float("inf")
    cost = [[inf] * count for _ in range(full + 1)]
    parent = [[-1] * count for _ in range(full + 1)]
    for first in range(count):
        cost[1 << first][first] = 0.0
    for mask in range(1, full + 1):
        for last in range(count):
            here = cost[mask][last]
            if here == inf:
                continue
            for nxt in range(count):
                if mask & (1 << nxt):
                    continue
                grown = mask | (1 << nxt)
                candidate = here + dist[last][nxt]
                if candidate < cost[grown][nxt]:
                    cost[grown][nxt], parent[grown][nxt] = candidate, last
    end = min(range(count), key=lambda j: cost[full][j])
    order: list[int] = []
    mask, node = full, end
    while node != -1:
        order.append(node)
        mask, node = mask ^ (1 << node), parent[mask][node]
    return tuple(reversed(order))


# ── T13 하루 마감 ────────────────────────────────────────────
def _day_end(day: date, parts: list[Part]) -> list[dict[str, Any]]:
    """그날 마지막 일정이 **하루 마감**(생성기의 하루 창 끝 `travel.day_window.default_end`, 22:00) 뒤에 끝나는가. `[체크리스트 T13]`

    생성기는 마감을 넘기면 거절하지만(「상품의 약속」) 고객·외부 에이전트가 준 일정에는 거절하지 않고 알린다 — 일부러 늦게까지 가는 일정(야경 · 공연)도 가능은 하다.
    끝 시각이 없으면 시작 시각으로 본다. 늦게 끝나는 항목을 모두 이름으로 말한다."""
    limit_text = str(get_guardrails().get("travel.day_window.default_end"))
    limit = datetime.combine(day, _clock(limit_text), tzinfo=KST)
    late = [p for p in parts if (p.ends_at or p.starts_at) > limit]
    if not late:
        return []
    last = max(late, key=lambda p: (p.ends_at or p.starts_at))
    finishes = last.ends_at or last.starts_at
    names = ", ".join(p.title for p in late)
    return [_warning(
        "past_day_end", day,
        f"{names} — {finishes:%H:%M}에 끝나 하루 마감({limit_text})을 넘는다",
        "마감 안에 끝나게 앞당기거나 줄인다(일부러 늦게까지 가는 일정이면 그대로 둔다)", [p.seq for p in late])]


# ── O4 식당 라스트오더 ───────────────────────────────────────
def _last_order(day: date, parts: list[Part]) -> list[dict[str, Any]]:
    """식당에 도착해 **주문할 시간이 촉박**한가. `[체크리스트 O4]` 대체 식당을 고를 때 쓰던 규칙(`replan.dining_fits` · `dining_warnings`)을 받은 일정에도 같은 기준으로 건다 —
    라스트오더를 **알면** 도착 + 20분이 그 시각을 넘을 때(브레이크 앞 · 영업 종료 앞), **모르면** 식사가 영업 종료 · 브레이크 시작 1시간 안에 끝날 때 「마지막 주문을 확인해 주세요」.

    ★영업하지 않는 시각 · 브레이크에 걸치는 것은 위반(`check_itinerary`)이 이미 막는다 — 위반이 있는 식사는 건너뛰고 여기서는 **라스트오더 이유**만 센다(같은 말을 두 번 하지 않는다).
    ★`[2026-10-03 적대 검토]` 라스트오더 값을 **모르면** 「라스트오더 촉박」이라고 지어 말하지 않는다(`last_order_shortfall` 은 아는 값만 센다) — 그때는 「마지막 주문을 확인해 주세요」뿐이다."""
    from .replan import dining_warnings, last_order_shortfall

    found: list[dict[str, Any]] = []
    for part in parts:
        if part.kind != MEAL_KIND or not part.place:
            continue
        if check_itinerary([part]):                 # 이미 위반(영업 안 함 · 브레이크에 걸침 …) — 위반이 말한다
            continue
        arrival = part.starts_at
        end = part.ends_at or part.starts_at + timedelta(minutes=_MEAL_FALLBACK_MIN)
        minutes = max(1, int((end - arrival).total_seconds() // 60))
        place = dict(part.place)
        why = last_order_shortfall(place, arrival)
        if why:
            found.append(_warning(
                "last_order_tight", day, f"{part.title}: {why}",
                "더 일찍 도착하게 앞당기거나 마지막 주문 시각을 미리 확인한다", [part.seq]))
        for note in dining_warnings(place, arrival, minutes):
            found.append(_warning("last_order_unknown", day, f"{part.title}: {note}", "방문 전에 마지막 주문 시각을 확인한다", [part.seq]))
    return found


__all__ = ["quality_warnings"]
