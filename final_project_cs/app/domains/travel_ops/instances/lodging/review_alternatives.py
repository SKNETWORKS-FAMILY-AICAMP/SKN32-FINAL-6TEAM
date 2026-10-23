# -*- coding: utf-8 -*-
"""확인 화면의 「다른 숙소」 후보 — 숙소 팀이 「바꿔 줘」에 쓰는 후보 고르기(`team._fresh_picks`)를 **등록 전 단계**에서도 부르는 어댑터. `[2026-10-16]`

숙소 비교(`booking.offers.search_stays`)를 **구글 호텔 목록으로 한 번만** 부르고(상세는 부르지 않는다 — 하루 한도),
팀의 고르기 순서(원래 가격대 → 기준점 가까운 곳 → 나머지)로 고른다. 지도에 올리려면 좌표가 있어야 해서 좌표가 있는 후보만 낸다.
★마이리얼트립은 부르지 않는다 — 목록에 좌표가 없어(상세를 읽어야 생긴다) 지도 후보가 될 수 없다. 구글 호텔(SerpApi 키)이 없으면 바깥에 나가지 않고 `None`.
좌표 있는 후보가 하나도 없으면 `None`(부르는 쪽이 자체 길로 간다)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .team import SEARCH_SIZE, _fresh_picks, _key


def rank(*, travel: Any, keyword: str, check_in: str, check_out: str, adults: int, anchor: tuple[float, float] | None = None,
         exclude_names: tuple[str, ...] = (), domestic: bool | None = True) -> dict[str, Any] | None:
    from app.domains.travel_ops.components.booking.offers import search_stays

    google = getattr(travel, "stay_google", None) if travel is not None else None
    if google is None:
        return None
    booked = search_stays(SimpleNamespace(stay_google=google), keyword=keyword, check_in=check_in, check_out=check_out, adults=adults,
                          domestic=domestic, size=SEARCH_SIZE)
    if not booked:
        return None
    dates, party = {"check_in": check_in, "check_out": check_out}, {"adults": adults, "children": None}
    center = {"latitude": anchor[0], "longitude": anchor[1], "kind": "원래 숙소", "usable": True} if anchor else None
    picks = _fresh_picks(booked, {_key(name) for name in exclude_names if name}, center, dates, party)
    shown = [p for p in picks if p.get("latitude") is not None and p.get("longitude") is not None]
    if not shown:
        return None
    return {"alternatives": [{"name": p["name"], "latitude": float(p["latitude"]), "longitude": float(p["longitude"]),
                              "source": p["source"], "price_per_night": p.get("price_per_night"), "rating": p.get("rating"),
                              "link": p.get("link")} for p in shown]}
