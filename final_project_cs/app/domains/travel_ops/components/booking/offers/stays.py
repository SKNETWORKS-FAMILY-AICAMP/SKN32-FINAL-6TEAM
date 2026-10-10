# -*- coding: utf-8 -*-
"""booking · offers — 숙소 비교. 마이리얼트립 목록과 구글 호텔 목록을 받고, 다른 곳 검색 링크를 붙인다. `[2026-10-10]`

전에 숙소 팀(`instances/lodging/team.py`) 안에 있던 「어느 소스를 부르나 · 다른 곳 링크」를 옮긴 것이다 — 동작은 그대로다.
어느 숙소를 보여 줄지(객실 없는 곳 건너뛰기 · 상세 확인 · 이미 보인 이름 빼기)는 추천이라 숙소 팀에 남긴다.

- 어댑터: 마이리얼트립 MCP(`travel_search.stay_search`) · SerpApi 구글 호텔(`stay_google.stay_search`). 없는 소스는 「조회 실패」로 센다.
- 두 소스의 숙소 이름이 달라(한국어 · 영어 · 지점 표기) 같은 숙소로 묶지 않는다 — 목록을 따로 돌려준다.
- 마이리얼트립이 429 뒤 쉬는 중이면 `resting` 으로 센다(어댑터가 `cooldown_seconds` 표시만 준다).
- 다른 곳 링크: 부킹닷컴만 — 2026-10-10 사용자 확인에서 지역 · 날짜 · 인원이 채워진 곳은 부킹닷컴뿐이었다
  (네이버 호텔 · 아고다는 첫 화면, 트립닷컴 숙소는 지역이 비어 결과 0).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote


def elsewhere(*, keyword: str, check_in: str, check_out: str, adults: int | None, children: int | None) -> list[dict[str, str]]:
    booking = (f"https://www.booking.com/searchresults.ko.html?ss={quote(keyword or '')}"
               f"&checkin={check_in}&checkout={check_out}"
               f"&group_adults={adults or 1}&no_rooms=1&group_children={children or 0}")
    return [{"name": "부킹닷컴", "url": booking}]


def _status(got: dict[str, Any] | None, *, absent: bool) -> dict[str, Any]:
    if absent or got is None:
        return {"status": "failed"}
    if got.get("cooldown_seconds"):
        return {"status": "resting", "cooldown_seconds": got["cooldown_seconds"]}
    return {"status": "ok", "count": len(got.get("stays") or [])}


def search_stays(travel: Any, *, keyword: str, check_in: str, check_out: str, adults: int | None = None,
                 children: int | None = None, domestic: bool | None = None, size: int = 20,
                 max_price: int | None = None, min_review_rating: float | None = None) -> dict[str, Any]:
    """숙소 비교 한 번. 돌려주는 것: `myrealtrip`(목록 그대로, 못 받았으면 `None`) · `google`(목록 그대로 또는 `None`) ·
    `sources`(소스별 `status` — ok · failed · resting) · `elsewhere` · `confirmed_at`."""
    query = {"keyword": keyword, "check_in": check_in, "check_out": check_out, "adults": adults, "children": children,
             "domestic": domestic, "size": size, "max_price": max_price, "min_review_rating": min_review_rating}
    wanted = {"myrealtrip": ("travel_search", query),
              # 구글 호텔은 국내 여부 · 최소 평점을 받지 않는다
              "google": ("stay_google", {key: query[key] for key in ("keyword", "check_in", "check_out", "adults",
                                                                      "children", "size", "max_price")})}
    results: dict[str, Any] = {}
    sources: dict[str, dict[str, Any]] = {}
    for name, (slot, arguments) in wanted.items():
        adapter = getattr(travel, slot, None) if travel is not None else None
        got = adapter.stay_search(**{key: value for key, value in arguments.items() if value is not None}) \
            if adapter is not None else None
        sources[name] = _status(got, absent=adapter is None)
        results[name] = got if sources[name]["status"] == "ok" else None
    return {"query": query, **results, "sources": sources,
            "elsewhere": elsewhere(keyword=keyword, check_in=check_in, check_out=check_out, adults=adults, children=children),
            "confirmed_at": datetime.now(UTC).isoformat(), "source": "booking"}


__all__ = ["elsewhere", "search_stays"]
