# -*- coding: utf-8 -*-
"""체인점 — 어느 지점인지 고르는 규칙. `[2026-10-07]` 순수 함수(DB · 네트워크 · 모델을 부르지 않는다).

★왜 따로 두나. 「12:30 스타벅스」가 아무 지점(관련도 1위 · 경복궁에서 8.9km)으로 **확인 없이** 확정됐다(장소 찾기 평가 v0,
  `eval/reports/2026-10-07_place_lookup_v0.md`). 원인은 셋이 겹친 것이다 — 지점 표시를 떼고 비교해 아무 지점이나 「같은 이름」이 됐고,
  앞 일정이 우리 장소 표에서 찾히면 근처 좌표가 넘어가지 않았고, 입력의 지점명(「강남역점」)을 위치 단서로 쓰지 않았다.
  부르는 쪽(접수 `places.resolve` · `pipeline._place_rows`)에 붙이기 전에 규칙만 먼저 굳혀 시험한다.

★네 단계 — 부르는 쪽은 이 순서로 쓴다(카카오 호출은 부르는 쪽이 한다).
    1  needs_branch_pick(query, hits)       지점을 골라야 하나 — 지점을 뗀 이름이 같은 음식점 · 카페가 둘 이상인 브랜드
    2  anchor_for(hint_point, neighbours)   기준 위치 — 지점명 > 확정된 앞뒤 일정 > 서로 붙어 있는 후보의 가운데 > 없음
    3  search_requests(chain, anchor)       기준 근처를 거리순 · 업종으로 다시 찾을 요청(반경을 넓혀 가며)
    4  pick_branch(chain, hits, anchor)     가장 가까운 지점 — **언제나 확인 필요**. 기준이 없거나 지점명이 맞는 곳이 없으면 고르지 않는다

★고르지 않는 것이 고르는 것보다 낫다 — 원문이 지점을 말하지 않았는데 기준 위치도 없으면 묻는다(「어느 지점인가요?」).
  다른 지점으로 일정을 짜면 이동 시간 · 영업 판정이 전부 그 지점 기준이 된다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Container, Iterable, Sequence

from .places import _BRANCH, _HANGUL, distance_m, normalize

#: 음식점 · 카페(카카오 `category_group_code`). 체인 판정 · 지점 찾기는 이 업종만 본다
FOOD_GROUPS = ("FD6", "CE7")
#: 지하철역 — 지점명(「강남역점」)의 위치를 찾을 때
STATION_GROUP = "SW8"
#: 지점 표시지만 위치가 아닌 말 — 단서로 쓰지 않는다
NOT_PLACE_BRANCH = frozenset({"본", "직영", "분", "별관", "신관", "본관", "1호", "2호", "3호"})
#: 기준 근처를 이 반경(미터)으로 차례로 넓혀 찾는다. 마지막 반경 밖은 고르지 않는다
RADII_M = (1_000, 3_000, 5_000)
#: 후보 중 고른 앞뒤 일정을 기준으로 쓰려면 그 후보들이 이 거리 안에 모여 있어야 한다(홍대입구역 출구들)
CLUSTER_M = 300
#: 고른 지점과 함께 보여 줄 다른 지점 수
ALTERNATIVES = 2


@dataclass(frozen=True)
class Chain:
    brand: str                  # 보여 줄 브랜드 이름(카카오가 쓴 표기, 지점 표시를 뗀 것) — 「스타벅스」
    brand_key: str              # 비교용 — normalize(brand)
    hint: str | None = None     # 입력의 지점명(위치 단서) — 「스타벅스 강남역점」 → 「강남역」
    romanized: bool = False     # 로마자 입력(「Starbucks」)을 결과로 체인이라 본 것
    #: 그 브랜드 지점들의 업종(카카오 FD6 · CE7) — 다시 찾을 때 이 업종만 묻는다(호출을 아낀다)
    groups: tuple[str, ...] = FOOD_GROUPS


@dataclass(frozen=True)
class Neighbour:
    """같은 날 앞뒤 일정 하나. `certain` = 확정된 곳(어디서 찾았든). 아니면 후보 중 고른 곳 — `spread_m` 이 그 후보들의 퍼짐."""
    latitude: float
    longitude: float
    certain: bool = True
    spread_m: float | None = None


@dataclass(frozen=True)
class Anchor:
    points: tuple[tuple[float, float], ...]
    source: str                 # branch_hint · neighbours · cluster
    note: str


@dataclass
class Pick:
    status: str                                 # picked · ask
    place: dict[str, Any] | None = None
    distance_m: float | None = None             # 기준 좌표들까지 평균 거리
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""
    needs_review: bool = True                   # ★체인은 언제나 확인 필요


# ── 이름 ───────────────────────────────────────────────────────
def brand_of(name: str) -> str:
    """지점 표시를 뗀 이름(보여 줄 표기). 「스타벅스 적선점」 → 「스타벅스」."""
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", name or "").strip()
    return _BRANCH.sub("", text).strip()


def _compact(name: str) -> str:
    """비교용 — `normalize` 와 같되 지점 표시를 떼지 않는다(「스타벅스 광화문점」 → 「스타벅스광화문점」)."""
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", name or "")
    return re.sub(r"[\s·\-_/]+", "", text).lower()


def branch_hint(query: str, brand_key: str) -> str | None:
    """입력에서 브랜드 뒤의 말을 꺼낸다 — 위치 단서. 없거나 위치가 아닌 말(본점 · 분점 · 1호점)이면 None.

    「스타벅스 강남역점」 · 「스타벅스강남역점」 · 「스타벅스 광화문」(「점」 없이) 모두 — 브랜드 뒤에 남는 말에서 끝의 「점」만 뗀다.
    ★위치가 아닌 말(「스타벅스 리저브」)도 단서로 나올 수 있다 — 위치를 못 찾으면 부르는 쪽은 앞뒤 일정을 기준으로 쓰고,
      고를 때는 이름에 그 말이 든 지점만 받으므로 엉뚱한 지점을 고르지 않는다(`pick_branch`).
    """
    text = _compact(query)
    if not brand_key or not text.startswith(brand_key):
        return None
    rest = text[len(brand_key):]
    if rest.endswith("점"):
        rest = rest[:-1]
    if len(rest) < 2 or rest in NOT_PLACE_BRANCH or re.fullmatch(r"\d+호?", rest):
        return None
    return rest


def _food(hits: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [h for h in hits if h.get("category_group") in FOOD_GROUPS]


def _key(hit: dict[str, Any]) -> str:
    return normalize(brand_of(hit.get("name") or ""))


# ── 1 체인인가 ─────────────────────────────────────────────────
def needs_branch_pick(query: str, hits: Sequence[dict[str, Any]], *, landmarks: Container[str] = ()) -> Chain | None:
    """**지점을 골라야 하는가.** 골라야 하면 `Chain`, 아니면 None — 부르는 쪽은 지금까지의 이름 찾기를 그대로 한다.

    ★None 이 「체인 브랜드가 아니다」라는 뜻은 아니다. 「스타벅스 광화문점」은 체인이지만 원문이 지점을 말했고 그 지점이
      결과에 하나 있으니 고를 것이 없다 — 그 지점이 답이다. 여기서 근처 지점을 고르면 오히려 다른 지점이 될 수 있다.

    한글 입력   결과의 음식점 · 카페 중 지점을 뗀 이름이 같은 곳이 **둘 이상**인 브랜드가 있고, 입력이 그 브랜드로 시작한다
                (「스타벅스」 · 「스타벅스 강남역점」 · 「스타벅스 광화문」). 입력과 띄어쓰기만 다른 이름이 결과에 **하나** 있으면
                (지점까지 말한 경우) 고르지 않는다.
    로마자 입력 결과가 **모두** 음식점 · 카페이고, 지점을 뗀 이름이 **절반 이상 · 둘 이상** 한 브랜드(「Starbucks」 → 「스타벅스 ○○점」들).
    ★`landmarks`(정규화한 관광지 이름 — 우리 장소 표 · 관광지 목록)에 브랜드가 있으면 고르지 않는다(관광지다).
      ☆`[실측 2026-10-07]` 「Gyeongbokgung」의 카카오 결과 5건이 모두 한식 체인 「경복궁 ○○점」 계열이었다(넷이 같은 이름).
        이름 하나로 모였다면 궁궐을 식당 체인으로 봤을 것이다. 로마자는 관광지 확인(`places._romanized`)이 먼저다.
    """
    food = _food(hits)
    if not query or len(food) < 2:
        return None
    if _HANGUL.search(query):
        text = _compact(query)
        counts: dict[str, int] = {}
        for h in food:
            counts[_key(h)] = counts.get(_key(h), 0) + 1
        brands = [k for k, n in counts.items() if n >= 2 and len(k) >= 2 and text.startswith(k)]
        if not brands:
            return None
        key = max(brands, key=len)              # 「스타벅스」와 「스타벅스리저브」가 다 있으면 긴 쪽
        if key in landmarks or normalize(query) in landmarks:
            return None                         # 「경복궁」 — 같은 이름 식당 체인이 있어도 관광지다
        exact = [h for h in hits if _compact(h.get("name") or "") == text]
        if len(exact) == 1 and text != key:
            return None                         # 지점까지 말했고 그 지점이 하나 — 그 지점이 답이다
        brand = brand_of(next(h for h in food if _key(h) == key)["name"])
        return Chain(brand=brand, brand_key=key, hint=branch_hint(query, key), groups=_groups(food, key))
    if len(food) != len(hits):
        return None                             # 음식점 · 카페가 아닌 결과가 섞였다 — 관광지일 수 있다
    counts: dict[str, int] = {}
    for hit in food:
        counts[_key(hit)] = counts.get(_key(hit), 0) + 1
    top = max(counts, key=lambda k: (counts[k], -len(k)))
    # ★`[2026-10-07]` 대부분(절반 이상 · 둘 이상)이 한 브랜드면 — 근처 결과에 「스타벅스 코엑스」 같은 이름이 섞인다
    if counts[top] < 2 or counts[top] * 2 < len(food):
        return None
    brand = brand_of(next(h for h in food if _key(h) == top)["name"])
    if normalize(brand) in landmarks:
        return None
    return Chain(brand=brand, brand_key=normalize(brand), romanized=True, groups=_groups(food, normalize(brand)))


def _groups(food: Sequence[dict[str, Any]], key: str) -> tuple[str, ...]:
    """그 브랜드 지점들의 업종 — 결과에 나온 순서대로(없으면 음식점 · 카페 둘 다)."""
    seen = []
    for hit in food:
        if _key(hit) == key and hit.get("category_group") not in seen:
            seen.append(hit["category_group"])
    return tuple(seen) or FOOD_GROUPS


# ── 2 기준 위치 ────────────────────────────────────────────────
def spread_m(points: Sequence[tuple[float, float]]) -> float:
    """좌표들이 얼마나 퍼져 있나 — 가장 먼 두 점 사이 거리(미터)."""
    widest = 0.0
    for i, a in enumerate(points):
        for b in points[i + 1:]:
            widest = max(widest, distance_m(a[0], a[1], b[0], b[1]))
    return widest


def anchor_for(*, hint_point: tuple[float, float] | None = None,
               neighbours: Sequence[Neighbour] = ()) -> Anchor | None:
    """어디 근처의 지점을 고를지. 없으면 None — 고르지 않고 묻는다.

    1  지점명 위치(부르는 쪽이 `Chain.hint` 를 역 · 장소로 찾은 좌표) — 원문이 말한 위치가 일정 앞뒤보다 앞선다
    2  확정된 앞뒤 일정 — **어디서 찾았든**(우리 장소 표 · 원장 · 관광지 · 카카오). 찾은 출처로 거르지 않는다
    3  후보 중 고른 앞뒤 일정 — 그 후보들이 `CLUSTER_M` 안에 모여 있을 때만(어느 후보든 위치가 거의 같다)
    """
    if hint_point is not None:
        return Anchor(points=(hint_point,), source="branch_hint", note="입력의 지점명 위치")
    certain = tuple((n.latitude, n.longitude) for n in neighbours if n.certain)
    if certain:
        return Anchor(points=certain, source="neighbours", note=f"앞뒤 일정 {len(certain)}곳")
    tight = tuple((n.latitude, n.longitude) for n in neighbours
                  if not n.certain and n.spread_m is not None and n.spread_m <= CLUSTER_M)
    if tight:
        return Anchor(points=tight, source="cluster", note=f"후보가 {CLUSTER_M}m 안에 모인 앞뒤 일정 {len(tight)}곳")
    return None


def centre(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


# ── 3 다시 찾을 요청 ───────────────────────────────────────────
def search_requests(chain: Chain, anchor: Anchor | None) -> list[dict[str, Any]]:
    """기준 근처를 다시 찾을 카카오 요청 — 부르는 쪽이 앞에서부터 부르다 고를 지점이 나오면 멈춘다.

    ★지금 카카오 어댑터(`kakao_local.search`)는 반경(20km 고정) · 업종 · 개수(5)를 받지 않는다. 이 요청을 그대로 쓰려면
      어댑터에 `radius` · `category_group_code` · `size` 를 더해야 한다(카카오 키워드 검색이 받는 값이다).
    """
    if anchor is None:
        return []
    at = centre(anchor.points)
    return [{"query": chain.brand, "near": at, "radius": radius, "sort": "distance", "size": 15,
             "category_group_code": group} for radius in RADII_M for group in chain.groups]


def hint_request(chain: Chain) -> dict[str, Any] | None:
    """지점명 위치를 찾을 요청 — 역이 먼저(「강남역」), 아니면 그 이름 그대로 서울에서."""
    if not chain.hint:
        return None
    return {"query": chain.hint, "category_group_code": STATION_GROUP if chain.hint.endswith("역") else None,
            "size": 1}


# ── 4 지점 고르기 ──────────────────────────────────────────────
def _mean_m(hit: dict[str, Any], points: Sequence[tuple[float, float]]) -> float:
    return sum(distance_m(hit["latitude"], hit["longitude"], lat, lon) for lat, lon in points) / len(points)


def pick_branch(chain: Chain, hits: Sequence[dict[str, Any]], anchor: Anchor | None) -> Pick:
    """기준에서 가장 가까운 지점. ★언제나 확인 필요 — 원문이 지점을 정확히 말한 경우는 `needs_branch_pick` 이 체인으로 보지 않는다.

    고르지 않는(ask) 경우
        기준이 없다                    — 서울 전역에서 아무 지점을 고르지 않는다. 관련도 순 앞의 지점들을 후보로만 준다
        지점명이 있는데 이름이 맞는 지점이 없다 — 「강남역점」이 없으면 근처 다른 지점을 고르지 않고 묻는다
        가장 가까운 지점도 마지막 반경 밖이다
    """
    branches = [h for h in _food(hits) if _key(h) == chain.brand_key and h.get("latitude") is not None]
    seen, unique = set(), []
    for h in branches:                                       # 반경을 넓혀 찾은 결과를 합치면 같은 지점이 겹친다
        ident = h.get("id") or (h["name"], round(h["latitude"], 5), round(h["longitude"], 5))
        if ident not in seen:
            seen.add(ident)
            unique.append(h)
    if not unique:
        return Pick(status="ask", note=f"「{chain.brand}」 지점을 찾지 못했다 — 어느 지점인지 물어 주세요")
    if anchor is None:
        return Pick(status="ask", alternatives=unique[:ALTERNATIVES + 1],
                    note=f"「{chain.brand}」는 지점이 여럿인데 기준이 될 앞뒤 일정이 없다 — 어느 지점인지 물어 주세요")

    ranked = sorted(unique, key=lambda h: _mean_m(h, anchor.points))
    if chain.hint:
        named = [h for h in ranked if chain.hint in normalize(h["name"]) or chain.hint in re.sub(r"\s+", "", h["name"])]
        if not named:
            return Pick(status="ask", alternatives=ranked[:ALTERNATIVES + 1],
                        note=f"「{chain.brand} {chain.hint}점」을 찾지 못했다 — 가까운 지점을 보여 드리니 골라 주세요")
        ranked = named + [h for h in ranked if h not in named]
    best = ranked[0]
    metres = _mean_m(best, anchor.points)
    if metres > RADII_M[-1]:
        return Pick(status="ask", alternatives=ranked[:ALTERNATIVES + 1], distance_m=metres,
                    note=f"가장 가까운 「{chain.brand}」도 {anchor.note}에서 {metres / 1000:.1f}km — 어느 지점인지 물어 주세요")
    return Pick(status="picked", place=best, distance_m=metres, alternatives=ranked[1:ALTERNATIVES + 1],
                note=f"「{chain.brand}」 지점 중 {anchor.note}에서 가장 가까운 「{best['name']}」(평균 {round(metres):,}m) — 다르면 고쳐 주세요")


__all__ = ["ALTERNATIVES", "Anchor", "CLUSTER_M", "Chain", "FOOD_GROUPS", "Neighbour", "Pick", "RADII_M",
           "anchor_for", "brand_of", "branch_hint", "centre", "needs_branch_pick", "hint_request", "pick_branch",
           "search_requests", "spread_m"]
