# -*- coding: utf-8 -*-
"""대체 식당이 원래 식당과 **얼마나 비슷한가** — 순수 함수. `[2026-10-07]`

★왜. 대체 후보가 종류를 보지 않아 삼계탕집 대신 카페가, 짜장면집 대신 백반집이 골라질 수 있었다(대체 식당 평가 v0 —
  `eval/reports/2026-10-07_dining_alternatives_v0.md`). 고객이 원한 것이 「그 가게」가 아니라 「그런 식사」라면
  비슷한 곳이 먼저다.

★등급(작을수록 비슷하다) — `likeness(original, candidate)`
    0 BRAND     지점을 뗀 이름이 같다(「스타벅스 가나점」 → 「스타벅스 다라점」) — 사실상 같은 곳
    1 DISH      대표 메뉴 말이 같다(이름 · 세부 분류에서 — 「토속촌삼계탕」 · 「OO삼계탕」)
    2 KIND      큰 종류가 같다(한식 · 중식 · 일식 · 양식 · 카페 …)
    3 UNKNOWN   어느 한쪽 종류를 모른다 — 다르다고 단정하지 않는다
    4 OTHER     종류가 다르다고 안다
  원래 식당의 종류를 모르면 모든 후보가 같은 등급(UNKNOWN)이다 — 순서는 거리 · 동선이 정한다.

★종류를 읽는 곳(있는 것만) — 장소 `attributes`
    cuisine     [큰 종류, 세부] — 평가 시나리오 · 앞으로 채울 칸
    category    원장 `dn_place.category`(「한식」 · 「카페디저트」 · 「미상」) 또는 카카오 분류(「음식점 > 한식 > 삼계탕」)
  원장에는 세부 종류 칸이 없다(`[실측 2026-10-07]` 영업 중 1,767곳 모두 큰 종류만). 세부는 이름의 메뉴 말로 짐작한다.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

BRAND, DISH, KIND, UNKNOWN, OTHER = 0, 1, 2, 3, 4

#: 여러 출처의 큰 종류 이름을 하나로. 없는 이름(기타 · 미상)은 모름이다
KINDS = {
    "한식": "한식", "중식": "중식", "중국식": "중식", "일식": "일식", "양식": "양식", "서양식": "양식",
    "카페": "카페", "카페디저트": "카페", "디저트": "카페", "커피전문점": "카페", "제과,베이커리": "카페",
    "분식": "분식", "치킨": "치킨", "패스트푸드": "패스트푸드", "술집": "술집", "아시아음식": "아시아음식",
}
#: 대표 메뉴 말 — 이름 · 세부 분류에서 찾는다. 긴 말이 먼저(「평양냉면」이 「냉면」보다)
DISHES = sorted({
    "삼계탕", "국밥", "순대국", "설렁탕", "곰탕", "감자탕", "해장국", "냉면", "평양냉면", "칼국수", "수제비", "만두",
    "백반", "한정식", "비빔밥", "불고기", "갈비", "삼겹살", "족발", "보쌈", "닭갈비", "찜닭", "닭한마리", "빈대떡",
    "떡볶이", "김밥", "짜장", "짬뽕", "딤섬", "마라", "훠궈", "초밥", "스시", "라멘", "우동", "돈가스", "돈카츠",
    "덮밥", "파스타", "피자", "스테이크", "버거", "햄버거", "브런치", "쌀국수", "커리", "치킨", "커피", "베이커리",
    "빵", "디저트", "아이스크림", "호프", "막걸리",
}, key=len, reverse=True)
#: 같은 메뉴로 보는 말
SAME_DISH = {"스시": "초밥", "돈카츠": "돈가스", "햄버거": "버거", "평양냉면": "냉면", "순대국": "국밥"}

_BRANCH = re.compile(r"\s*(본점|직영점|분점|별관|본관|신관|\S+점)$")


def _attrs(place: Mapping[str, Any]) -> Mapping[str, Any]:
    return place.get("attributes") or {}


def brand_key(name: str | None) -> str:
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", name or "").strip()
    return re.sub(r"[\s·\-_/]+", "", _BRANCH.sub("", text)).lower()


def kind_of(place: Mapping[str, Any]) -> str | None:
    """큰 종류. 모르면 None."""
    attributes = _attrs(place)
    cuisine = attributes.get("cuisine")
    if isinstance(cuisine, (list, tuple)) and cuisine:
        return KINDS.get(str(cuisine[0]).strip(), str(cuisine[0]).strip() or None)
    category = attributes.get("category")
    if isinstance(category, str) and category.strip():
        parts = [p.strip() for p in category.split(">") if p.strip()]
        for part in parts:                       # 「음식점 > 한식 > 삼계탕」 → 한식 · 「카페 > 커피전문점」 → 카페
            if part in KINDS:
                return KINDS[part]
    return None


def dish_of(place: Mapping[str, Any]) -> str | None:
    """대표 메뉴 말. 세부 분류가 먼저, 없으면 이름에서. 모르면 None."""
    attributes = _attrs(place)
    texts = []
    cuisine = attributes.get("cuisine")
    if isinstance(cuisine, (list, tuple)) and len(cuisine) > 1:
        texts.append(str(cuisine[1]))
    category = attributes.get("category")
    if isinstance(category, str) and ">" in category:
        texts.append(category.split(">")[-1])
    texts.append(str(place.get("name") or ""))
    for text in texts:
        compact = re.sub(r"\s+", "", text)
        for dish in DISHES:
            if dish in compact:
                return SAME_DISH.get(dish, dish)
    return None


def likeness(original: Mapping[str, Any], candidate: Mapping[str, Any]) -> int:
    """비슷한 정도(0 이 가장 비슷하다). 위 등급표."""
    a, b = brand_key(original.get("name")), brand_key(candidate.get("name"))
    if a and a == b:
        return BRAND
    dish_a, dish_b = dish_of(original), dish_of(candidate)
    if dish_a and dish_a == dish_b:
        return DISH
    kind_a, kind_b = kind_of(original), kind_of(candidate)
    if kind_a is None or kind_b is None:
        return UNKNOWN
    return KIND if kind_a == kind_b else OTHER


__all__ = ["BRAND", "DISH", "KIND", "OTHER", "UNKNOWN", "brand_key", "dish_of", "kind_of", "likeness"]
