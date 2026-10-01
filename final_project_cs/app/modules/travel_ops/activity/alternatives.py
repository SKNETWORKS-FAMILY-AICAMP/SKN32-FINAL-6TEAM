# -*- coding: utf-8 -*-
"""대체 장소 후보 — 「문제있음」 판정 뒤에만 부른다(wiki/teams/activity.md
「대안 생성 규칙」 ①~④).

★**계산만 한다. LLM 을 부르지 않는다.** 후보 풀(카탈로그 행)을 받아
  거르고 줄 세울 뿐이다 — 풀을 어디서 읽어 오는지(DB조회·기타지도API)는
  이 모듈의 경계 밖이다(작업자 A 범위).

★**여기서 고른 후보도 판정이 아니다.** 통지 전에 `check_feasible`(①검증
  규칙)을 다시 통과해야 한다(v11 §5). 이 모듈의 ① 가용성 필터는 **명백히
  닫힌 곳을 미리 빼는 것**일 뿐이다.

| 단계 | 함수 | 하는 일 |
|---|---|---|
| ① 가용성 | `closed_on`·`open_at` | 휴무일(`closed_days`)과 운영시간(`business_hours`)을 **가장 먼저** 본다 — 명백히 닫힌 곳만 뺀다 |
| ② 유사도 | `similar` | 원래 장소와 같은 갈래(분류·시군구)만 남긴다 |
| ③ 선호도 | `FALLBACK_DROPS` | 0건이면 정해진 순서로 필드를 빼고 다시 거른다 |
| ④ 순위 | `rank_alternatives` | 같은 브랜드·같은 시군구 먼저, 그다음 좌표 직선거리 오름차순 1·2·3위 |

★브랜드 매장(올리브영·다이소·아트박스·무신사)은 같은 브랜드가 가장 비슷한 대체다.
  다만 **같은 시군구 안의 같은 브랜드만** 앞세운다 — 시군구 밖의 같은 브랜드보다
  더 가까운 다른 매장이 있으면 그쪽이 낫다(거리도 무시 못 한다).
"""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

#: ② 유사도에 쓰는 필드. 전부 TourAPI 원본 필드명이다(CSV 컬럼과 같다).
SIMILARITY_FIELDS = ("contenttypeid", "lclsSystm1", "lclsSystm2", "lclsSystm3", "sigungucode")

#: ③ 선호도별 폴백 — 0건이면 **앞에서부터 한 단계씩** 뺀다(2026-10-01 팀 합의).
#:  - 이동 1순위: 시군구 고정 → ①소분류 ②중분류 ③대분류(+타입)를 뺀다.
#:  - 활동 1순위: 대분류(+타입) 고정 → ①소분류 ②중분류 ③시군구를 뺀다.
#:  ★타입(`contenttypeid`)은 **대분류와 한 묶음**이다. 대분류와 거의 1:1 이라(관광타입 38=쇼핑, 15=행사,
#:   14=문화시설) 따로 풀 이유가 없고, 풀어야 한다면 대분류와 함께 **맨 마지막**에 푼다.
FALLBACK_DROPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "mobility": (("lclsSystm3",), ("lclsSystm2",), ("lclsSystm1", "contenttypeid")),
    "activity": (("lclsSystm3",), ("lclsSystm2",), ("sigungucode",)),
}

_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
_WEEKLY = re.compile(r"매주\s*([^/<(※]*)")
_RANGE = re.compile(r"([월화수목금토일])요일\s*~\s*([월화수목금토일])요일")
_SINGLE = re.compile(r"([월화수목금토일])요일")
#: 원문이 「모른다」고 말하는 표현. 여기 걸리면 열었다고도 닫았다고도 안 한다.
_UNKNOWN_MARKERS = ("상이", "참조", "확인", "문의")


def closed_on(closed_days: str | None, at: datetime) -> bool | None:
    """`at` 요일이 원문의 정기휴무 요일인가. 모르면 `None`.

    ★`_weekday_closure_match`와 같은 원칙 — **"매주 <요일>" 하나만** 본다.
      "단, 공휴일과 겹치면 개방" 같은 예외 조건, 1월 1일·설·추석 같은 날짜
      휴무는 반영하지 않는다. `~` 범위("매주 토요일~일요일")와 "주말"만
      펴서 읽는다 — 그 이상은 파싱하지 않는다.

    | 원문 | 결과 |
    |---|---|
    | 비었음 · "점포별 상이" · "홈페이지 참조" | `None` (모름) |
    | "연중무휴" · "매주 월요일"(요청이 토요일) | `False` |
    | "매주 월요일"(요청이 월요일) · "주말"(요청이 일요일) | `True` |
    """
    text = (closed_days or "").strip()
    if not text or any(marker in text for marker in _UNKNOWN_MARKERS):
        return None
    when = at if at.tzinfo else at.replace(tzinfo=UTC)
    closed: set[int] = set()
    if "주말" in text:
        closed |= {5, 6}
    for weekly in _WEEKLY.findall(text):
        for start, end in _RANGE.findall(weekly):
            i, j = _WEEKDAYS.index(start), _WEEKDAYS.index(end)
            span = range(i, j + 1) if i <= j else [*range(i, 7), *range(0, j + 1)]
            closed |= set(span)
        closed |= {_WEEKDAYS.index(d) for d in _SINGLE.findall(weekly)}
    return when.weekday() in closed


KST = timezone(timedelta(hours=9))
_TIME_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[~\-–]\s*(\d{1,2}):(\d{2})")
_ALWAYS_OPEN = re.compile(r"상시|24\s*시간")
#: 이 말이 있으면 원문을 해석하지 않는다(모름). 층·시설·계절·휴게처럼 시간표 하나로 못 읽는 표현이다.
_HOURS_UNSURE = ("상이", "참조", "확인", "문의", "별도", "변동", "브레이크", "휴게", "[", "<br", "하계", "동계",
                 "성수기", "비수기", "라스트", "예약")
_DAY_TOKENS = {"평일": {0, 1, 2, 3, 4}, "주말": {5, 6}, "매일": set(range(7))}
_DAY_CHARS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
_HOLIDAY = re.compile(r"공휴일|휴일")
_DAY_RANGE = re.compile(r"([월화수목금토일])(?:요일)?\s*[~\-]\s*([월화수목금토일])(?:요일)?")


def _hours_segment_days(label: str) -> set[int] | None:
    """구간 앞뒤 글자에서 적용 요일을 읽는다. 라벨이 없으면 매일. 못 읽는 글자가 남으면 `None`."""
    rest = _HOLIDAY.sub("", label)
    days: set[int] = set()
    for first, last in _DAY_RANGE.findall(rest):          # 「월~금」 「금~월」
        i, j = _DAY_CHARS[first], _DAY_CHARS[last]
        days |= set(range(i, j + 1)) if i <= j else {*range(i, 7), *range(0, j + 1)}
    rest = _DAY_RANGE.sub("", rest)
    for token, covered in _DAY_TOKENS.items():
        if token in rest:
            days |= covered
            rest = rest.replace(token, "")
    rest = rest.replace("요일", "")
    for char, index in _DAY_CHARS.items():
        if char in rest:
            days.add(index)
            rest = rest.replace(char, "")
    if re.search(r"[가-힣A-Za-z0-9]", rest):
        return None
    if not days:
        return set(range(7)) if not _HOLIDAY.search(label) else set()
    return days


def open_at(business_hours: str | None, at: datetime) -> bool | None:
    """`at` 시각에 열려 있나. 확실히 읽을 수 있을 때만 답하고 그 밖은 `None`(모름).

    ★`closed_on` 과 같은 원칙 — **명백히 닫힌 곳(False)만** 후보에서 뺀다. 모르면 남기고 표시한다.
    읽는 것: 「상시 개방」·「24시간」, 「HH:MM~HH:MM」(여러 개 · 자정 넘김 · 24:00 끝), 「/」로 나뉜 구간 앞의
      요일 라벨(평일·주말·월~일·매일). 입장마감 같은 괄호 설명은 뗀다.
    안 읽는 것(`None`): 비었음, 「점포별 상이」·「브레이크」·계절·층별처럼 `_HOURS_UNSURE` 에 걸리는 말,
      시간이 아닌 글자가 라벨에 남는 구간, `at` 요일에 맞는 구간이 없을 때, 공휴일 구간의 시간이 다를 때.
    ★시각은 한국 시간(KST)으로 읽는다. 시간대 없는 `at` 도 KST 로 본다 — 원문이 한국 현지 시각이다.
    """
    raw = (business_hours or "").strip()
    if not raw or any(marker in raw for marker in _HOURS_UNSURE):
        return None
    text = re.sub(r"\(.*?\)", "", raw).strip()
    ranges_found = _TIME_RANGE.search(text) is not None
    if _ALWAYS_OPEN.search(text):
        return True if not ranges_found else None
    if not ranges_found:
        return None

    local = at.astimezone(KST) if at.tzinfo else at
    now_min, weekday = local.hour * 60 + local.minute, local.weekday()

    matched: list[tuple[int, int]] = []
    holiday: set[tuple[int, int]] = set()
    for segment in re.split(r"[/;\n]", text):
        segment = segment.strip()
        if not segment:
            continue
        spans = [(int(a) * 60 + int(b), int(c) * 60 + int(d)) for a, b, c, d in _TIME_RANGE.findall(segment)]
        if not spans:
            return None
        days = _hours_segment_days(_TIME_RANGE.sub("", segment))
        if days is None:
            return None
        if _HOLIDAY.search(segment):
            holiday.update(spans)
        if weekday in days:
            matched.extend(spans)
    if not matched:
        return None
    if holiday and not holiday <= set(matched):
        return None      # ★공휴일 시간이 따로 있으면 오늘이 공휴일인지 몰라 단정하지 않는다
    for start, end in matched:
        inside = (start <= now_min < end) if start < end else (now_min >= start or now_min < end)
        if inside:
            return True
    return False


def _norm(value: Any) -> str:
    return str(value or "").strip()


def similar(origin: dict[str, Any], pool: list[dict[str, Any]],
            fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """`fields`가 원래 장소와 **모두** 같은 후보만. 원래 장소 쪽 값이 비면 그
    필드는 비교하지 않는다(모르는 값끼리 "같다"고 읽지 않는다)."""
    keys = [f for f in fields if _norm(origin.get(f))]
    return [c for c in pool if all(_norm(c.get(f)) == _norm(origin.get(f)) for f in keys)]


def preference_from_survey(survey: dict[str, Any] | None) -> str | None:
    """설문 `priority`(앞이 더 중요) 중 먼저 나오는 `activity`·`mobility` 를 선호도로. 없으면 `None`.

    ★`food` 는 이 팀 몫이 아니라 건너뛴다. `None`(무응답)이면 `rank_alternatives` 가 폴백을 쓰지 않는다.
    """
    for area in (survey or {}).get("priority") or []:
        if area in FALLBACK_DROPS:
            return area
    return None


def same_brand_nearby(origin: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """원래 장소가 브랜드 매장이고, 후보가 **같은 브랜드이면서 같은 시군구**인가.

    ★브랜드나 시군구를 모르면 `False` — 모르는 값끼리 「같다」고 읽지 않는다(`similar` 와 같은 원칙).
    """
    brand, gu = _norm(origin.get("brand")), _norm(origin.get("sigungucode"))
    return bool(brand and gu
                and _norm(candidate.get("brand")) == brand
                and _norm(candidate.get("sigungucode")) == gu)


def distance_km(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    """`mapx`(경도)·`mapy`(위도) 직선거리(haversine). 좌표가 없으면 `None`."""
    try:
        lon1, lat1 = float(a["mapx"]), float(a["mapy"])
        lon2, lat2 = float(b["mapx"]), float(b["mapy"])
    except (KeyError, TypeError, ValueError):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def rank_alternatives(origin: dict[str, Any], pool: list[dict[str, Any]], at: datetime,
                      *, preference: str | None = None, limit: int = 3) -> dict[str, Any]:
    """①~④를 차례로 적용해 1·2·3위를 낸다.

    `preference`: `"mobility"`(이동 중요) · `"activity"`(활동 중요) · `None`(설문 무응답).
    ★`None`이면 ③을 **아예 안 쓴다** — 우선순위를 임의로 가정하지 않고
      5개 필드 전부로 한 번만 거르며, 0건이어도 폴백하지 않는다.

    반환값의 `dropped_fields`·`availability`는 어느 조건을 풀었는지·무엇을
    모르는지를 숨기지 않으려고 둔다.
    """
    if preference is not None and preference not in FALLBACK_DROPS:
        raise ValueError(f"unknown preference: {preference!r}")

    origin_id = _norm(origin.get("contentid"))
    # ① 가용성 — **가장 먼저.** 휴무 요일(`closed_on`)이거나 운영시간 밖(`open_at`)인 곳만 뺀다.
    #    모름(None)은 남기되 표시한다.
    open_pool: list[tuple[dict[str, Any], bool | None, bool | None]] = []
    for candidate in pool:
        if origin_id and _norm(candidate.get("contentid")) == origin_id:
            continue
        closed = closed_on(candidate.get("closed_days"), at)
        if closed is True:
            continue
        in_hours = open_at(candidate.get("business_hours"), at)
        if in_hours is False:
            continue
        open_pool.append((candidate, closed, in_hours))
    candidates = [c for c, _, _ in open_pool]
    closed_state = {id(c): closed for c, closed, _ in open_pool}
    hours_state = {id(c): in_hours for c, _, in_hours in open_pool}

    def confirmed(c: dict[str, Any]) -> bool:
        return closed_state[id(c)] is False or hours_state[id(c)] is True

    # ②·③ 유사도 + 폴백 — 폴백은 `FALLBACK_DROPS` 의 순서대로 한 묶음씩 뺀다.
    fields = list(SIMILARITY_FIELDS)
    dropped: list[str] = []
    matched = similar(origin, candidates, tuple(fields))
    if preference:
        for group in FALLBACK_DROPS[preference]:
            if matched:
                break
            dropped.extend(group)
            fields = [f for f in fields if f not in group]
            matched = similar(origin, candidates, tuple(fields))

    # ④ 순위 — 같은 브랜드·같은 시군구 먼저, 그다음 거리 오름차순.
    #    좌표가 없는 후보는 뒤로, 가용성 모름은 확인된 것 뒤로.
    def sort_key(c: dict[str, Any]) -> tuple:
        d = distance_km(origin, c)
        return (not confirmed(c), not same_brand_nearby(origin, c),
                d is None, d if d is not None else 0.0)

    ranked = sorted(matched, key=sort_key)[:limit]
    return {
        "preference": preference,
        "matched_fields": list(fields),
        "dropped_fields": dropped,
        "total_matched": len(matched),
        "alternatives": [
            {"rank": i + 1,
             "contentid": c.get("contentid"),
             "title": c.get("title"),
             "distance_km": None if (d := distance_km(origin, c)) is None else round(d, 2),
             # ★가장 강한 확인만 말한다: 휴무 요일이 아님 → `open_weekday`, 그것은 모르지만 운영시간 안 → `open_at_time`
             "availability": ("open_weekday" if closed_state[id(c)] is False
                              else "open_at_time" if hours_state[id(c)] is True else "unconfirmed"),
             "closed_days": c.get("closed_days") or None,
             "business_hours": c.get("business_hours") or None}
            for i, c in enumerate(ranked)
        ],
    }
