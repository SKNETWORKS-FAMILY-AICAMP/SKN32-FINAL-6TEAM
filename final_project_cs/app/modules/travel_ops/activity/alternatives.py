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
| ① 가용성 | `closed_on` | `closed_days` 원문에서 "매주 <요일>" 만 좁게 본다 |
| ② 유사도 | `similar` | 원래 장소와 같은 갈래(분류·시군구)만 남긴다 |
| ③ 선호도 | `FIELD_PRIORITY` | 0건이면 우선순위 낮은 필드부터 빼고 다시 거른다 |
| ④ 순위 | `rank_alternatives` | 좌표 직선거리 오름차순 1·2·3위 |
"""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any

#: ② 유사도에 쓰는 필드. 전부 TourAPI 원본 필드명이다(CSV 컬럼과 같다).
SIMILARITY_FIELDS = ("contenttypeid", "lclsSystm1", "lclsSystm2", "lclsSystm3", "sigungucode")

#: ③ 선호도별 우선순위(앞이 높다). 폴백은 **뒤에서부터** 뺀다. 맨 앞 필드는
#:  「고정값」이라 폴백으로도 빠지지 않는다(activity.md 다이어그램).
FIELD_PRIORITY: dict[str, tuple[str, ...]] = {
    "mobility": ("sigungucode", "lclsSystm1", "lclsSystm2", "lclsSystm3", "contenttypeid"),
    "activity": ("lclsSystm1", "sigungucode", "lclsSystm2", "lclsSystm3", "contenttypeid"),
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


def _norm(value: Any) -> str:
    return str(value or "").strip()


def similar(origin: dict[str, Any], pool: list[dict[str, Any]],
            fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """`fields`가 원래 장소와 **모두** 같은 후보만. 원래 장소 쪽 값이 비면 그
    필드는 비교하지 않는다(모르는 값끼리 "같다"고 읽지 않는다)."""
    keys = [f for f in fields if _norm(origin.get(f))]
    return [c for c in pool if all(_norm(c.get(f)) == _norm(origin.get(f)) for f in keys)]


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
    if preference is not None and preference not in FIELD_PRIORITY:
        raise ValueError(f"unknown preference: {preference!r}")

    origin_id = _norm(origin.get("contentid"))
    # ① 가용성 — 명백히 닫힌 곳(True)만 뺀다. 모름(None)은 남기되 표시한다.
    open_pool: list[tuple[dict[str, Any], bool | None]] = []
    for candidate in pool:
        if origin_id and _norm(candidate.get("contentid")) == origin_id:
            continue
        closed = closed_on(candidate.get("closed_days"), at)
        if closed is True:
            continue
        open_pool.append((candidate, closed))
    candidates = [c for c, _ in open_pool]
    closed_state = {id(c): closed for c, closed in open_pool}

    # ②·③ 유사도 + 폴백
    fields = FIELD_PRIORITY[preference] if preference else SIMILARITY_FIELDS
    dropped: list[str] = []
    matched = similar(origin, candidates, fields)
    if preference:
        # 맨 앞(고정값)은 남기고 뒤에서부터 하나씩 뺀다.
        while not matched and len(fields) > 1:
            dropped.append(fields[-1])
            fields = fields[:-1]
            matched = similar(origin, candidates, fields)

    # ④ 순위 — 거리 오름차순. 좌표가 없는 후보는 뒤로, 가용성 모름은 확인된 것 뒤로.
    def sort_key(c: dict[str, Any]) -> tuple:
        d = distance_km(origin, c)
        return (closed_state[id(c)] is None, d is None, d if d is not None else 0.0)

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
             "availability": "unconfirmed" if closed_state[id(c)] is None else "open_weekday",
             "closed_days": c.get("closed_days") or None,
             "business_hours": c.get("business_hours") or None}
            for i, c in enumerate(ranked)
        ],
    }
