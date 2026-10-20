# -*- coding: utf-8 -*-
"""같은 장소 판정 — 이름이 달라도 **같은 곳**인가(「N서울타워」 = 「남산서울타워」). `[2026-10-19 사용자 결정]`

☆왜: 대체 장소 후보에서 「이미 일정에 있는 곳」을 뺄 때 contentid 와 **이름 문자열 완전 일치**만 봤다. 일정의 카카오 장소
  「N서울타워」(contentid 없음)와 원장의 「남산서울타워」는 이름이 달라 안 빠지고 같은 곳이 또 추천됐다. 이름이 닮은 것만으로는
  같은 곳을 가를 수 없다 — 남산도서관 · 용산도서관(유사도 0.92 · 121m)이 다른 곳이고 남산서울타워 · N서울타워(0.80)가 같은 곳이다.
  그래서 **사람이 확인한 별칭**(`place_aliases`)이 같은 곳을 확정하고, 이름 유사도는 「같을 수도 있다」는 표시까지만 한다.

세 단계다(`verdict`):
    same       — 같은 contentid, 정규화한 이름이 같다, 또는 한쪽 이름이 다른 쪽 장소의 **별칭**이다(좌표를 알면 `ALIAS_MAX_M` 안일 때). 후보에서 뺀다.
    ambiguous  — `NEAR_M` 안이고 이름이 `NAME_SIM_MIN` 이상 닮았는데 이름이 다르고 별칭도 아니다. **빼지 않는다** — 경고로만 센다.
    different  — 그 밖(좌표를 모르거나 `NEAR_M` 밖이거나 이름이 안 닮았다).

★**계산만 한다.** LLM · DB 를 부르지 않는다. 애매한 쌍을 LLM 에게 묻는 방식은 만들었다가 지웠다(2026-10-19 사용자 결정) —
  정확도를 잴 수 없고 별칭이 같은 문제를 확정적으로 푼다. 애매한 쌍이 자주 나오면 별칭을 더한다.
★짐작으로 후보를 지우지 않는다. 잘못 빼도 후보가 한 곳 줄 뿐이지만, 잘못 남겨도 같은 곳이 한 번 더 나올 뿐이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.domains.travel_ops.components.intake.places import distance_m, normalize_full

from . import place_aliases

#: 같은 곳일 수 있는 거리(m). ★우리가 고른 값 — 카카오 · 관광공사 좌표는 입구 · 주차장 차이로 수십~수백 m 어긋난다.
#:  `itinerary_changes.SAME_SITE_M`(30m)와 다르다 — 그쪽은 「확실히 같은 곳」, 여기는 「같을 수도 있는 거리」다.
NEAR_M = 300
#: 별칭이 맞아도 두 좌표가 이보다 멀면 같은 곳으로 보지 않는다(m). ★우리가 고른 값 — 별칭은 사람이 확인했지만 같은 이름의 **다른 곳**(다른 동네 · 다른 도시)이
#:  카카오로 들어올 수 있다. 큰 장소(공원 · 궁 · 산)는 카카오와 관광공사의 대표 좌표가 1km 넘게 어긋나서 300m 로는 맞는 별칭을 놓친다. 좌표를 모르면 별칭을 믿는다.
ALIAS_MAX_M = 3000
#: 이름이 이만큼 닮아야 「애매함」으로 센다(공통 부분열 ÷ 짧은 이름). ★우리가 고른 값 — 이름만으로는 같은 곳을 못 가르므로 표시용 문턱일 뿐이다.
NAME_SIM_MIN = 0.8
#: 이름 두 개가 이보다 짧으면 닮았는지 따지지 않는다(「남산」 같은 짧은 말이 아무 데나 붙는다)
MIN_NAME_LEN = 3


@dataclass(frozen=True)
class Spot:
    """같은 곳인지 따질 장소 하나 — 일정 항목 또는 대체 후보."""
    name: str
    latitude: float | None
    longitude: float | None
    content_id: str | None = None
    kind: str | None = None          # 분류 — 없어도 된다


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def spot_of(place: dict[str, Any] | None) -> Spot | None:
    """일정 항목의 장소(`name` · `latitude` · `longitude` · `source_content_id`)나 후보 행(`title` · `mapy` · `mapx` · `contentid`)을 `Spot` 으로."""
    if not isinstance(place, dict):
        return None
    attributes = place.get("attributes") if isinstance(place.get("attributes"), dict) else {}
    name = str(place.get("name") or place.get("title") or "").strip()
    if not name:
        return None
    content_id = place.get("source_content_id") or attributes.get("source_content_id") or place.get("contentid")
    lat = _float(place.get("latitude") if place.get("latitude") is not None else place.get("mapy"))
    lon = _float(place.get("longitude") if place.get("longitude") is not None else place.get("mapx"))
    kind = place.get("lclsSystm3") or place.get("lclsSystm2") or place.get("kind")
    return Spot(name, lat, lon, str(content_id) if content_id else None, str(kind) if kind else None)


def _lcs(a: str, b: str) -> int:
    previous = [0] * (len(b) + 1)
    for ca in a:
        current = [0]
        for j, cb in enumerate(b, start=1):
            current.append(previous[j - 1] + 1 if ca == cb else max(previous[j], current[-1]))
        previous = current
    return previous[-1]


def name_similarity(a: str, b: str) -> float:
    """정규화한 두 이름의 닮은 정도 0~1 — 공통 부분열 길이 ÷ 짧은 이름. 한쪽이 다른 쪽의 부분열이면 1."""
    key_a, key_b = normalize_full(a), normalize_full(b)
    if min(len(key_a), len(key_b)) < MIN_NAME_LEN:
        return 0.0
    return _lcs(key_a, key_b) / min(len(key_a), len(key_b))


def distance_between(a: Spot, b: Spot) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    return distance_m(a.latitude, a.longitude, b.latitude, b.longitude)


def verdict(item: Spot, candidate: Spot, aliases: place_aliases.AliasTable = place_aliases.EMPTY) -> str:
    """`same` · `different` · `ambiguous` — 규칙만. 모르는 값은 같다고 읽지 않는다. `aliases` 는 후보 조회가 읽은 별칭 표."""
    if item.content_id and item.content_id == candidate.content_id:
        return "same"
    a, b = normalize_full(item.name), normalize_full(candidate.name)
    if not a or not b:
        return "different"
    # ★`[2026-10-19]` 사람이 확인한 별칭이 먼저다 — 이름이 완전히 달라도(「N서울타워」 = 「남산서울타워」) 같은 곳이다.
    #   다만 좌표를 둘 다 알고 `ALIAS_MAX_M` 보다 멀면 같은 이름의 다른 곳일 수 있다 — `ambiguous`(별칭은 이름만 증명하고 위치는 증명하지 않는다)
    if aliases.is_alias_of(item.name, candidate.content_id) or aliases.is_alias_of(candidate.name, item.content_id):
        d = distance_between(item, candidate)
        return "ambiguous" if d is not None and d > ALIAS_MAX_M else "same"   # 멀면 같은 이름의 다른 곳일 수 있다 — 빼지 않고 경고로 센다
    if a == b:
        return "same"                      # 지금까지의 동작 — 이름이 같으면 같은 곳으로 본다(거리와 상관없이)
    d = distance_between(item, candidate)
    if d is None or d > NEAR_M:
        return "different"
    return "ambiguous" if name_similarity(item.name, candidate.name) >= NAME_SIM_MIN else "different"


def split(items: Iterable[Spot], candidates: list[dict[str, Any]],
          aliases: place_aliases.AliasTable = place_aliases.EMPTY) -> tuple[list[dict[str, Any]], int, int]:
    """후보를 `(남길 후보, `same` 이라 뺀 수, `ambiguous` 라 남긴 수)` 로 가른다."""
    spots = [s for s in items if s is not None]
    kept: list[dict[str, Any]] = []
    removed = maybe = 0
    for row in candidates:
        cand = spot_of(row)
        if cand is None or not spots:
            kept.append(row)
            continue
        states = [verdict(item, cand, aliases) for item in spots]
        if "same" in states:
            removed += 1
            continue
        maybe += "ambiguous" in states
        kept.append(row)
    return kept, removed, maybe
